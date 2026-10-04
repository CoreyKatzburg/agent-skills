# DynamoDB, explained (video)

A narrated, animated explainer video (about 5 minutes, 1920×1080) that teaches what Amazon DynamoDB is and how it works. It's written like a senior engineer walking an intern through it from first principles: tables and items, primary keys, partitions and hashing, scaling, the three copies of your data, read consistency, ways to read, hot partitions, pricing, strengths and weaknesses, and when to use it.

The video is code, not a video-editor project. That makes it easy to change one sentence or one animation and render again.

## How it's made

| Step | File | What it does |
| --- | --- | --- |
| 1. Script | `narration.json` | What the narrator says, split into 14 scenes, plus the voice and speaking speed. |
| 2. Voice | `make_voiceover.py` | Turns each scene into speech and records **when every word is spoken**. Writes `build/voiceover.wav` and `build/timeline.js`. |
| 3. Pictures | `video.html` | Draws each scene with HTML and SVG. Each animation is tied to a spoken word, for example "show the hash box when the narrator says *hash*". So if the voice changes speed, the animations stay in sync on their own. |
| 4. Render | `render_video.js` | Opens the page in headless Chromium, takes a picture of every frame (30 per second), and has `ffmpeg` join the frames and the voice into `build/dynamodb-explainer.mp4`. |

Why time animations to words instead of to seconds? A new voice, or one edited sentence, changes every timing after it. Tying each animation to a word means nothing needs to be re-timed by hand.

## Rebuild it

```bash
npm install                       # fonts (Inter, JetBrains Mono)
pip install kokoro soundfile      # free local voice (needs PyTorch: pip install torch --index-url https://download.pytorch.org/whl/cpu)
python3 make_voiceover.py         # 1-2 minutes on a laptop CPU
node render_video.js              # about 10 minutes with 4 workers
```

You also need `ffmpeg`, plus Playwright with Chromium (`npm i -g playwright && npx playwright install chromium`).

Useful extras:

- `node render_video.js --stills 12,95.5` saves single frames to `build/stills/`, for checking a layout without a full render.
- Open `video.html?preview` through any local web server (for example `npx serve .`), then click to watch it live with the voice. Add `&t=120` to start at 2:00.

## Choosing a voice

`make_voiceover.py --provider <name> [--voice <voice>] [--speed 1.15]`

The voice comes from `kokoro_voice` in `narration.json` (currently the male voice `am_michael`), and speed from `speaking_speed` (currently 1.3). Kokoro's speed control moves in steps rather than smoothly, so measure before trusting a number: for `am_michael`, 1.3 is about the same pace as `af_heart` at 1.2, while 1.34 is about 12% faster. `--speed` overrides it for one run. The animations follow the words, so any speed stays in sync.

| Provider | Cost / setup | Quality | Notes |
| --- | --- | --- | --- |
| `kokoro` (default) | Free, runs locally, no key | Very good | Voice set in `narration.json` (`am_michael`). Others: `af_heart`, `af_bella`, `am_fenrir`, `bf_emma`. Gives exact word timings. |
| `openrouter` | Free tier, needs `OPENROUTER_API_KEY` | Excellent | Uses `fish-audio/s2.1-pro-free:free`. Fish Audio doesn't return word timings, so a local speech-recognition model (`pip install faster-whisper`) listens to each clip to find them. |
| `edge` | Free, no key (`pip install edge-tts`) | OK | Microsoft Edge's online voices. Kept as a fallback. |

To use Fish Audio, store the key as an environment variable named `OPENROUTER_API_KEY`. For a Claude Code cloud environment: open the environment settings, choose **Edit**, and add the variable. New sessions pick it up. Never commit the key. Then run:

```bash
pip install faster-whisper
python3 make_voiceover.py --provider openrouter
node render_video.js
```

## Changing the content

- **Change a sentence:** edit `narration.json`, then rerun both commands. If you remove a word that a scene uses as a cue, the renderer stops and names the missing cue, so nothing goes out of sync silently.
- **Change a picture:** each scene is a `SCENE_BUILDERS.<scene id>` function in `video.html`. It builds its pieces once, then returns an `update(time, at)` function. `at("word")` gives the moment that word is spoken.

## Facts used

- Prime Day 2025 peak of 151 million DynamoDB requests per second: AWS News Blog, "AWS services scale to new heights for Prime Day 2025: key metrics and milestones".
- Three copies across availability zones, leader-based writes acknowledged by a majority, strongly consistent reads served by the leader, and eventually consistent reads costing half: the DynamoDB developer guide and the 2022 USENIX ATC paper *Amazon DynamoDB: A Scalable, Predictably Performant, and Fully Managed NoSQL Database Service*.
