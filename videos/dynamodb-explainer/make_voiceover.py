"""Generate the narration audio and a word-level timeline for the DynamoDB video.

For every scene in narration.json this script:
  1. turns the scene's text into speech with the chosen voice provider,
  2. records when each word is spoken (used to time animations and captions),
  3. stitches all scene clips into one voiceover track with short pauses between them.

Voice providers (pick with --provider):
  kokoro      Free, open-source model that runs on this machine. No API key. (default)
  openrouter  Fish Audio S2.1 Pro (free tier) through OpenRouter. Needs OPENROUTER_API_KEY.
              Fish Audio does not report word timings, so a local speech-recognition
              model (faster-whisper) listens to the clip and finds them.
  edge        Microsoft Edge's online voices. No API key, lower quality.

Outputs (all in build/):
  audio/<scene_id>.wav   one clip per scene
  voiceover.wav          the full narration track
  timeline.js            scene start times and word timings, loaded by video.html
"""

import argparse
import asyncio
import difflib
import io
import json
import os
import re
import ssl
import subprocess
import urllib.request
import wave
from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent
BUILD_FOLDER = PROJECT_FOLDER / "build"
AUDIO_FOLDER = BUILD_FOLDER / "audio"
SAMPLE_RATE = 24000
LEAD_IN_SECONDS = 0.35
END_CARD_EXTRA_SECONDS = 3.0

DEFAULT_VOICES = {
    "kokoro": "af_heart",
    "openrouter": None,  # let Fish Audio use its default narrator voice
    "edge": "en-US-AndrewNeural",
}

# Some networks route HTTPS through a proxy with its own certificate authority.
CERTIFICATE_BUNDLE = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
SSL_CONTEXT = (
    ssl.create_default_context(cafile=CERTIFICATE_BUNDLE)
    if Path(CERTIFICATE_BUNDLE).exists()
    else ssl.create_default_context()
)


def normalize_word(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def decode_to_pcm(audio_bytes):
    """Decode any audio file (mp3, wav, ...) into raw 16-bit mono samples at SAMPLE_RATE."""
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-i", "-", "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        input=audio_bytes,
        check=True,
        capture_output=True,
    ).stdout


def write_wav(path, pcm_samples):
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm_samples)


def silence(seconds):
    return b"\x00\x00" * int(round(seconds * SAMPLE_RATE))


def match_timings_to_script(timed_words, script_text):
    """Give every word of the script a start and end time.

    timed_words is whatever the voice provider (or speech recognizer) heard, which can
    differ slightly from the script ("Dynamo DB" instead of "DynamoDB"). We line the two
    word lists up, copy times across where they match, and fill any gaps by spreading
    the missing words evenly between their neighbours. Script words keep their
    punctuation so the captions read naturally.
    """
    script_tokens = script_text.split()
    script_keys = [normalize_word(token) for token in script_tokens]
    heard_keys = [normalize_word(word["text"]) for word in timed_words]

    starts = [None] * len(script_tokens)
    ends = [None] * len(script_tokens)
    matcher = difflib.SequenceMatcher(a=script_keys, b=heard_keys, autojunk=False)
    for script_from, heard_from, size in matcher.get_matching_blocks():
        for offset in range(size):
            starts[script_from + offset] = timed_words[heard_from + offset]["start"]
            ends[script_from + offset] = timed_words[heard_from + offset]["end"]

    # A script word with no exact match ("DynamoDB" heard as "dynamo" + "db") takes its
    # time from the neighbouring words that did match.
    known_points = [index for index, value in enumerate(starts) if value is not None]
    if not known_points:
        raise RuntimeError("Could not match any spoken words to the script.")
    first_time = timed_words[0]["start"]
    last_time = timed_words[-1]["end"]
    for index in range(len(script_tokens)):
        if starts[index] is not None:
            continue
        previous_known = max((point for point in known_points if point < index), default=None)
        next_known = min((point for point in known_points if point > index), default=None)
        gap_start = ends[previous_known] if previous_known is not None else first_time
        gap_end = starts[next_known] if next_known is not None else last_time
        gap_first_index = (previous_known + 1) if previous_known is not None else 0
        gap_last_index = (next_known - 1) if next_known is not None else len(script_tokens) - 1
        gap_size = gap_last_index - gap_first_index + 1
        slot = (gap_end - gap_start) / gap_size
        position = index - gap_first_index
        starts[index] = gap_start + slot * position
        ends[index] = gap_start + slot * (position + 1)

    return [
        {
            "text": token,
            "display": token,
            "key": normalize_word(token),
            "start": round(starts[index], 3),
            "end": round(ends[index], 3),
        }
        for index, token in enumerate(script_tokens)
        if normalize_word(token)
    ]


# ---------------------------------------------------------------------------
# Voice providers. Each returns (pcm_samples, timed_words) for one scene.
# timed_words is a list of {"text", "start", "end"} in seconds from the clip start.
# ---------------------------------------------------------------------------


class KokoroVoice:
    def __init__(self, voice_name):
        from kokoro import KPipeline

        self.pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
        self.voice_name = voice_name

    def speak(self, text):
        import numpy

        audio_parts = []
        timed_words = []
        clip_offset_seconds = 0.0
        # Kokoro reads long text in chunks; each chunk's word times start at zero.
        for chunk in self.pipeline(text, voice=self.voice_name, speed=1.0):
            chunk_audio = chunk.audio.numpy()
            for token in chunk.tokens:
                if token.start_ts is None or not normalize_word(token.text):
                    continue
                timed_words.append(
                    {
                        "text": token.text,
                        "start": clip_offset_seconds + token.start_ts,
                        "end": clip_offset_seconds + (token.end_ts or token.start_ts),
                    }
                )
            audio_parts.append(chunk_audio)
            clip_offset_seconds += len(chunk_audio) / SAMPLE_RATE
        samples = numpy.concatenate(audio_parts)
        pcm_samples = (numpy.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
        return pcm_samples, timed_words


class WordTimingListener:
    """Finds when each word is spoken in a clip, using a small local speech-recognition model."""

    def __init__(self):
        from faster_whisper import WhisperModel

        self.model = WhisperModel("small.en", device="cpu", compute_type="int8")

    def listen(self, wav_path):
        segments, _ = self.model.transcribe(str(wav_path), word_timestamps=True, beam_size=5)
        return [
            {"text": word.word.strip(), "start": word.start, "end": word.end}
            for segment in segments
            for word in segment.words
        ]


class OpenRouterFishVoice:
    MODEL = "fish-audio/s2.1-pro-free:free"
    ENDPOINT = "https://openrouter.ai/api/v1/audio/speech"

    def __init__(self, voice_name):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise SystemExit("OPENROUTER_API_KEY is not set. Add it to the environment and try again.")
        self.voice_name = voice_name
        self.listener = WordTimingListener()

    def speak(self, text):
        request_body = {"model": self.MODEL, "input": text, "response_format": "wav"}
        if self.voice_name:
            request_body["voice"] = self.voice_name
        request = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(request_body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, context=SSL_CONTEXT, timeout=300) as response:
            pcm_samples = decode_to_pcm(response.read())
        temporary_path = AUDIO_FOLDER / "_listening.wav"
        write_wav(temporary_path, pcm_samples)
        timed_words = self.listener.listen(temporary_path)
        temporary_path.unlink()
        return pcm_samples, timed_words


class EdgeVoice:
    TICKS_PER_SECOND = 10_000_000  # edge-tts reports times in 100-nanosecond ticks

    def __init__(self, voice_name):
        import edge_tts.communicate as edge_tts_communicate

        # edge-tts pins its own certificate list; use the system bundle instead.
        edge_tts_communicate._SSL_CTX = SSL_CONTEXT
        self.voice_name = voice_name

    def speak(self, text):
        return asyncio.run(self._speak(text))

    async def _speak(self, text):
        import edge_tts

        speaker = edge_tts.Communicate(
            text, self.voice_name, boundary="WordBoundary", proxy=os.environ.get("HTTPS_PROXY")
        )
        audio_bytes = io.BytesIO()
        timed_words = []
        async for chunk in speaker.stream():
            if chunk["type"] == "audio":
                audio_bytes.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_seconds = chunk["offset"] / self.TICKS_PER_SECOND
                timed_words.append(
                    {
                        "text": chunk["text"],
                        "start": start_seconds,
                        "end": start_seconds + chunk["duration"] / self.TICKS_PER_SECOND,
                    }
                )
        return decode_to_pcm(audio_bytes.getvalue()), timed_words


VOICE_PROVIDERS = {"kokoro": KokoroVoice, "openrouter": OpenRouterFishVoice, "edge": EdgeVoice}


def main():
    argument_parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    argument_parser.add_argument("--provider", choices=VOICE_PROVIDERS, default="kokoro")
    argument_parser.add_argument("--voice", help="Voice name for the provider (see README).")
    arguments = argument_parser.parse_args()

    narration = json.loads((PROJECT_FOLDER / "narration.json").read_text())
    AUDIO_FOLDER.mkdir(parents=True, exist_ok=True)
    voice_name = arguments.voice or DEFAULT_VOICES[arguments.provider]
    voice = VOICE_PROVIDERS[arguments.provider](voice_name)

    voiceover_samples = bytearray()
    timeline_scenes = []
    scene_start_seconds = 0.0

    for scene_number, scene in enumerate(narration["scenes"]):
        clip_samples, timed_words = voice.speak(scene["text"])
        write_wav(AUDIO_FOLDER / f"{scene['id']}.wav", clip_samples)
        clip_seconds = len(clip_samples) / 2 / SAMPLE_RATE
        script_words = match_timings_to_script(timed_words, scene["text"])

        is_last_scene = scene_number == len(narration["scenes"]) - 1
        tail_seconds = narration["pause_after_scene_seconds"] + (END_CARD_EXTRA_SECONDS if is_last_scene else 0)
        scene_duration = LEAD_IN_SECONDS + clip_seconds + tail_seconds
        voiceover_samples += silence(LEAD_IN_SECONDS) + clip_samples + silence(tail_seconds)

        # Word times become relative to the start of the scene (including the lead-in).
        for word in script_words:
            word["start"] = round(word["start"] + LEAD_IN_SECONDS, 3)
            word["end"] = round(word["end"] + LEAD_IN_SECONDS, 3)

        timeline_scenes.append(
            {
                "id": scene["id"],
                "title": scene["title"],
                "start": round(scene_start_seconds, 3),
                "duration": round(scene_duration, 3),
                "words": script_words,
            }
        )
        print(f"{scene['id']:<12} {clip_seconds:6.2f}s  {len(script_words)} words")
        scene_start_seconds += scene_duration

    write_wav(BUILD_FOLDER / "voiceover.wav", bytes(voiceover_samples))
    timeline = {
        "voice": f"{arguments.provider}:{voice_name or 'default'}",
        "totalDuration": round(scene_start_seconds, 3),
        "scenes": timeline_scenes,
    }
    (BUILD_FOLDER / "timeline.js").write_text("window.TIMELINE = " + json.dumps(timeline, indent=1) + ";\n")
    print(f"total        {scene_start_seconds:6.2f}s")


if __name__ == "__main__":
    main()
