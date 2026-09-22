#!/usr/bin/env python3
"""Export the current Cursor, Claude Code, or Codex transcript to Markdown."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


MAX_TOOL_OUTPUT_CHARS = 3000
MAX_TOOL_ARGUMENT_CHARS = 1500


@dataclass
class TranscriptEntry:
    """One rendered transcript block."""

    heading: str
    text: str
    timestamp: str | None


@dataclass
class TranscriptMetadata:
    """Session metadata displayed at the top of the transcript."""

    app_name: str
    session_id: str
    started_at: str | None
    ended_at: str | None
    cwd: str | None = None
    branch: str | None = None


def parse_timestamp(timestamp: str | None) -> str:
    """Convert an ISO timestamp into the local timezone."""

    if not timestamp:
        return ""

    try:
        parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return timestamp

    return parsed_timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def truncate_text(text: str, max_chars: int) -> str:
    """Trim long tool arguments and outputs without hiding that truncation occurred."""

    stripped_text = text.strip()
    if len(stripped_text) <= max_chars:
        return stripped_text

    return f"{stripped_text[:max_chars]}..."


def render_json_block(value: Any, max_chars: int = MAX_TOOL_ARGUMENT_CHARS) -> str:
    """Render structured values inside fenced blocks."""

    rendered_json = json.dumps(value, indent=2, ensure_ascii=False)
    return f"```json\n{truncate_text(rendered_json, max_chars)}\n```"


def format_command(command: Any) -> str:
    """Render shell commands consistently across Claude and Codex tool calls."""

    if isinstance(command, str):
        return command
    if isinstance(command, list):
        return " ".join(shlex.quote(str(part)) for part in command)
    return json.dumps(command, ensure_ascii=False)


def format_tool_use(name: str, tool_input: dict[str, Any]) -> str:
    """Format a Claude tool call into readable Markdown."""

    lines = [f"**Tool: `{name}`**"]

    if name == "Bash" and "command" in tool_input:
        lines.append(f"```bash\n{format_command(tool_input['command'])}\n```")
    elif name in {"Read", "Write", "Edit"} and "file_path" in tool_input:
        lines.append(f"File: `{tool_input['file_path']}`")
    elif name in {"Grep", "Glob"} and "pattern" in tool_input:
        lines.append(f"Pattern: `{tool_input['pattern']}`")
    elif name == "Agent" and "prompt" in tool_input:
        description = tool_input.get("description", "")
        if description:
            lines.append(f"Agent: {description}")
        prompt = truncate_text(str(tool_input["prompt"]), MAX_TOOL_ARGUMENT_CHARS)
        lines.append(f"> {prompt}")
    else:
        lines.append(render_json_block(tool_input))

    return "\n".join(lines)


def format_tool_result(content: Any) -> str:
    """Format Claude or Codex tool output into a collapsible block."""

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") in {"text", "input_text", "output_text"}:
                text_value = str(item.get("text", "")).strip()
                if text_value:
                    text_parts.append(text_value)
        rendered_content = "\n".join(text_parts)
    else:
        rendered_content = str(content).strip()

    if not rendered_content:
        return ""

    truncated_output = truncate_text(rendered_content, MAX_TOOL_OUTPUT_CHARS)
    return (
        "<details>\n"
        "<summary>Tool result</summary>\n\n"
        f"```\n{truncated_output}\n```\n"
        "</details>"
    )


def extract_text_from_content(content: Any) -> str:
    """Extract readable text from Claude or Codex message content blocks."""

    if isinstance(content, str):
        return content.strip()

    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            stripped_block = block.strip()
            if stripped_block:
                parts.append(stripped_block)
            continue

        if not isinstance(block, dict):
            continue

        block_type = block.get("type", "")
        if block_type in {"text", "input_text", "output_text"}:
            text_value = str(block.get("text", "")).strip()
            if text_value:
                parts.append(text_value)
        elif block_type == "tool_use":
            tool_name = str(block.get("name", "unknown"))
            tool_input = block.get("input", {})
            if isinstance(tool_input, dict):
                parts.append(format_tool_use(tool_name, tool_input))
        elif block_type == "tool_result":
            formatted_result = format_tool_result(block.get("content", ""))
            if formatted_result:
                parts.append(formatted_result)

    return "\n\n".join(parts)


def detect_session_format(session_path: Path) -> str:
    """Identify whether the JSONL file came from Cursor, Claude Code, or Codex."""

    with session_path.open("r", encoding="utf-8") as session_file:
        for line in session_file:
            stripped_line = line.strip()
            if not stripped_line:
                continue

            payload = json.loads(stripped_line)
            if payload.get("role") in {"user", "assistant"} and isinstance(payload.get("message"), dict):
                return "cursor"

            message_type = payload.get("type", "")
            if message_type in {"user", "assistant"}:
                return "claude"
            if message_type in {"session_meta", "response_item", "event_msg", "turn_context"}:
                return "codex"
            if message_type:
                continue

    raise ValueError(f"Transcript file is empty: {session_path}")


def build_claude_transcript(session_path: Path) -> tuple[TranscriptMetadata, list[TranscriptEntry]]:
    """Parse a Claude Code session JSONL file."""

    entries: list[TranscriptEntry] = []
    session_id = ""
    git_branch = ""
    started_at = ""
    ended_at = ""

    with session_path.open("r", encoding="utf-8") as session_file:
        for line in session_file:
            stripped_line = line.strip()
            if not stripped_line:
                continue

            payload = json.loads(stripped_line)
            message_type = payload.get("type", "")
            timestamp = payload.get("timestamp", "")

            if not session_id:
                session_id = str(payload.get("sessionId", ""))
            if not git_branch:
                git_branch = str(payload.get("gitBranch", ""))
            if not started_at and timestamp:
                started_at = timestamp
            if timestamp:
                ended_at = timestamp

            if message_type == "user":
                content = payload.get("message", {}).get("content", "")
                text = extract_text_from_content(content)
                if text:
                    entries.append(TranscriptEntry(heading="User", text=text, timestamp=timestamp))
            elif message_type == "assistant":
                content = payload.get("message", {}).get("content", [])
                text = extract_text_from_content(content)
                if text:
                    entries.append(TranscriptEntry(heading="Assistant", text=text, timestamp=timestamp))

    metadata = TranscriptMetadata(
        app_name="Claude Code",
        session_id=session_id or session_path.stem,
        started_at=started_at or None,
        ended_at=ended_at or None,
        branch=git_branch or None,
    )
    return metadata, entries


def extract_cursor_user_text(text: str) -> tuple[str, str | None]:
    """Pull the user query and timestamp out of Cursor wrapper tags."""

    timestamp_match = re.search(r"<timestamp>(.*?)</timestamp>", text, flags=re.DOTALL)
    timestamp = timestamp_match.group(1).strip() if timestamp_match else None

    query_match = re.search(r"<user_query>(.*?)</user_query>", text, flags=re.DOTALL)
    if query_match:
        display_text = query_match.group(1).strip()
    else:
        display_text = re.sub(
            r"<manually_attached_skills>.*?</manually_attached_skills>",
            "",
            text,
            flags=re.DOTALL,
        )
        display_text = re.sub(r"<timestamp>.*?</timestamp>", "", display_text, flags=re.DOTALL)
        display_text = display_text.strip()

    if "<side_chat_boundary>" in text:
        display_text = "Side chat (continues from the parent conversation)\n\n" + display_text

    return display_text, timestamp


def build_cursor_transcript(session_path: Path) -> tuple[TranscriptMetadata, list[TranscriptEntry]]:
    """Parse a Cursor agent-transcripts JSONL file."""

    entries: list[TranscriptEntry] = []
    started_at = ""
    ended_at = ""

    with session_path.open("r", encoding="utf-8") as session_file:
        for line in session_file:
            stripped_line = line.strip()
            if not stripped_line:
                continue

            payload = json.loads(stripped_line)
            if payload.get("type") == "turn_ended":
                continue

            role = payload.get("role", "")
            if role not in {"user", "assistant"}:
                continue

            content = payload.get("message", {}).get("content", [])
            timestamp = None
            if role == "user":
                raw_text = extract_text_from_content(content)
                text, timestamp = extract_cursor_user_text(raw_text)
            else:
                text = extract_text_from_content(content)

            if timestamp:
                if not started_at:
                    started_at = timestamp
                ended_at = timestamp

            if text:
                heading = "User" if role == "user" else "Assistant"
                entries.append(TranscriptEntry(heading=heading, text=text, timestamp=timestamp))

    metadata = TranscriptMetadata(
        app_name="Cursor",
        session_id=session_path.stem,
        started_at=started_at or None,
        ended_at=ended_at or None,
    )
    return metadata, entries


def parse_codex_tool_arguments(arguments: Any) -> Any:
    """Decode function arguments when Codex stores them as a JSON string."""

    if not isinstance(arguments, str):
        return arguments

    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        return arguments


def format_codex_function_call(name: str, arguments: Any) -> str:
    """Format a Codex tool call as Markdown."""

    decoded_arguments = parse_codex_tool_arguments(arguments)
    lines = [f"**Tool: `{name}`**"]

    if isinstance(decoded_arguments, dict):
        if name == "exec_command" and "cmd" in decoded_arguments:
            lines.append(f"```bash\n{decoded_arguments['cmd']}\n```")
        elif name == "shell" and "command" in decoded_arguments:
            lines.append(f"```bash\n{format_command(decoded_arguments['command'])}\n```")
        else:
            lines.append(render_json_block(decoded_arguments))
    elif isinstance(decoded_arguments, str) and decoded_arguments.strip():
        lines.append(f"```text\n{truncate_text(decoded_arguments, MAX_TOOL_ARGUMENT_CHARS)}\n```")

    return "\n".join(lines)


def build_codex_transcript(session_path: Path) -> tuple[TranscriptMetadata, list[TranscriptEntry]]:
    """Parse a Codex session JSONL file."""

    entries: list[TranscriptEntry] = []
    tool_names_by_call_id: dict[str, str] = {}

    session_id = ""
    started_at = ""
    ended_at = ""
    cwd = ""
    branch = ""

    with session_path.open("r", encoding="utf-8") as session_file:
        for line in session_file:
            stripped_line = line.strip()
            if not stripped_line:
                continue

            payload = json.loads(stripped_line)
            timestamp = payload.get("timestamp", "")
            if timestamp:
                ended_at = timestamp

            message_type = payload.get("type", "")
            if message_type == "session_meta":
                session_meta = payload.get("payload", {})
                session_id = str(session_meta.get("id", ""))
                started_at = str(session_meta.get("timestamp", "") or timestamp)
                cwd = str(session_meta.get("cwd", ""))
                git_info = session_meta.get("git", {})
                if isinstance(git_info, dict):
                    branch = str(git_info.get("branch", ""))
                continue

            if message_type != "response_item":
                continue

            response_item = payload.get("payload", {})
            response_type = response_item.get("type", "")

            if response_type == "message":
                role = response_item.get("role", "")
                if role not in {"user", "assistant"}:
                    continue

                content = response_item.get("content", [])
                text = extract_text_from_content(content)
                if text:
                    heading = "User" if role == "user" else "Assistant"
                    entries.append(TranscriptEntry(heading=heading, text=text, timestamp=timestamp))
            elif response_type == "function_call":
                tool_name = str(response_item.get("name", "unknown"))
                call_id = str(response_item.get("call_id", "") or response_item.get("callId", ""))
                if call_id:
                    tool_names_by_call_id[call_id] = tool_name

                formatted_call = format_codex_function_call(
                    name=tool_name,
                    arguments=response_item.get("arguments", ""),
                )
                entries.append(
                    TranscriptEntry(
                        heading=f"Tool: {tool_name}",
                        text=formatted_call,
                        timestamp=timestamp,
                    )
                )
            elif response_type == "function_call_output":
                call_id = str(response_item.get("call_id", "") or response_item.get("callId", ""))
                tool_name = tool_names_by_call_id.get(call_id, "unknown")
                formatted_output = format_tool_result(response_item.get("output", ""))
                if formatted_output:
                    entries.append(
                        TranscriptEntry(
                            heading=f"Tool Output: {tool_name}",
                            text=formatted_output,
                            timestamp=timestamp,
                        )
                    )

    metadata = TranscriptMetadata(
        app_name="Codex",
        session_id=session_id or session_path.stem,
        started_at=started_at or None,
        ended_at=ended_at or None,
        cwd=cwd or None,
        branch=branch or None,
    )
    return metadata, entries


def convert_session(session_path: Path, output_path: Path) -> Path:
    """Convert a Cursor, Claude Code, or Codex session JSONL file to Markdown."""

    session_format = detect_session_format(session_path)
    if session_format == "cursor":
        metadata, entries = build_cursor_transcript(session_path)
    elif session_format == "claude":
        metadata, entries = build_claude_transcript(session_path)
    elif session_format == "codex":
        metadata, entries = build_codex_transcript(session_path)
    else:
        raise ValueError(f"Unsupported transcript format: {session_format}")

    if not entries:
        raise ValueError(f"No transcript entries were found in {session_path}")

    lines = [f"# {metadata.app_name} Transcript", ""]
    lines.append(f"**Session:** `{metadata.session_id}`")
    if metadata.cwd:
        lines.append(f"**Working Directory:** `{metadata.cwd}`")
    if metadata.branch:
        lines.append(f"**Branch:** `{metadata.branch}`")
    if metadata.started_at:
        lines.append(f"**Started:** {parse_timestamp(metadata.started_at)}")
    if metadata.ended_at:
        lines.append(f"**Ended:** {parse_timestamp(metadata.ended_at)}")
    lines.append(f"**Entries:** {len(entries)}")
    lines.extend(["", "---", ""])

    for entry in entries:
        header = f"## {entry.heading}"
        formatted_timestamp = parse_timestamp(entry.timestamp)
        if formatted_timestamp:
            header += f"  <sub>{formatted_timestamp}</sub>"

        lines.extend([header, "", entry.text, "", "---", ""])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def workspace_slug(path: Path) -> str:
    """Match Cursor's ~/.cursor/projects/<slug> encoding of a workspace path."""

    return str(path).lstrip("/").replace("/", "-")


def find_current_cursor_session() -> tuple[str, str, Path]:
    """Locate the newest parent Cursor agent transcript for this workspace."""

    projects_root = Path.home() / ".cursor" / "projects"
    if not projects_root.is_dir():
        raise FileNotFoundError(f"No Cursor projects directory at {projects_root}")

    parent_transcripts: list[Path] = []
    for jsonl_path in projects_root.glob("*/agent-transcripts/*/*.jsonl"):
        if "subagents" in jsonl_path.parts:
            continue
        if jsonl_path.stem != jsonl_path.parent.name:
            continue
        parent_transcripts.append(jsonl_path)

    if not parent_transcripts:
        raise FileNotFoundError(
            f"No parent Cursor transcripts found under {projects_root}/*/agent-transcripts/"
        )

    cwd_slug = workspace_slug(Path.cwd())

    def score(jsonl_path: Path) -> tuple[int, float]:
        project_slug = jsonl_path.parents[2].name
        if project_slug == cwd_slug:
            match_score = 3
        elif cwd_slug.startswith(f"{project_slug}-") or project_slug.startswith(f"{cwd_slug}-"):
            match_score = 2
        else:
            match_score = 0
        return (match_score, jsonl_path.stat().st_mtime)

    best_path = max(parent_transcripts, key=score)
    return "Cursor", best_path.stem, best_path


def find_current_session_path() -> tuple[str, str, Path]:
    """Locate the active transcript file for Cursor, Claude Code, or Codex."""

    codex_thread_id = os.getenv("CODEX_THREAD_ID")
    if codex_thread_id:
        codex_sessions_dir = Path.home() / ".codex" / "sessions"
        matches = sorted(codex_sessions_dir.rglob(f"*{codex_thread_id}*.jsonl"))
        if matches:
            return "Codex", codex_thread_id, matches[-1]
        raise FileNotFoundError(
            f"Detected Codex thread {codex_thread_id}, but no JSONL was found under {codex_sessions_dir}"
        )

    claude_session_id = os.getenv("CLAUDE_SESSION_ID")
    if claude_session_id:
        claude_projects_dir = Path.home() / ".claude" / "projects"
        exact_matches = sorted(claude_projects_dir.rglob(f"{claude_session_id}.jsonl"))
        if exact_matches:
            return "Claude Code", claude_session_id, exact_matches[-1]

        fallback_matches = sorted(claude_projects_dir.rglob(f"*{claude_session_id}*.jsonl"))
        if fallback_matches:
            return "Claude Code", claude_session_id, fallback_matches[-1]

        raise FileNotFoundError(
            f"Detected Claude session {claude_session_id}, but no JSONL was found under {claude_projects_dir}"
        )

    try:
        return find_current_cursor_session()
    except FileNotFoundError as cursor_error:
        raise EnvironmentError(
            "Could not detect the current runtime. Expected CODEX_THREAD_ID or "
            f"CLAUDE_SESSION_ID, or a Cursor transcript under ~/.cursor/projects/*/agent-transcripts/. {cursor_error}"
        ) from cursor_error


def export_current_transcript(target_directory: str) -> Path:
    """Export the active Cursor, Claude Code, or Codex transcript into the target directory."""

    expanded_directory = Path(target_directory).expanduser()
    if not expanded_directory.is_dir():
        raise NotADirectoryError(f"Output directory does not exist: {expanded_directory}")

    _, session_id, session_path = find_current_session_path()
    output_path = expanded_directory / f"transcript-{session_id}.md"
    return convert_session(session_path=session_path, output_path=output_path)


def main() -> None:
    """Support direct conversion mode and auto-discovery export mode."""

    if len(sys.argv) == 2:
        output_path = export_current_transcript(sys.argv[1])
        print(f"Transcript written to: {output_path}")
        return

    if len(sys.argv) == 3:
        session_path = Path(sys.argv[1]).expanduser()
        output_path = Path(sys.argv[2]).expanduser()

        if not session_path.is_file():
            raise FileNotFoundError(f"Session file not found: {session_path}")
        if not output_path.parent.is_dir():
            raise NotADirectoryError(f"Output directory does not exist: {output_path.parent}")

        written_path = convert_session(session_path=session_path, output_path=output_path)
        print(f"Transcript written to: {written_path}")
        return

    raise SystemExit(
        f"Usage:\n"
        f"  {sys.argv[0]} <target-directory>\n"
        f"  {sys.argv[0]} <session.jsonl> <output.md>"
    )


if __name__ == "__main__":
    main()
