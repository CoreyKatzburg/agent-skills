---
name: transcript
description: Export the current Cursor, Claude Code, or Codex conversation transcript to a Markdown file. Use when the user wants to save, export, or share the current conversation.
metadata:
  short-description: Export the current conversation transcript
---

# Transcript Export

Export the current conversation to a readable Markdown file. Works in Cursor, Claude Code, and Codex.

## Requirements

The user must provide a target directory. If they have not named one, ask for it before doing anything else.

Examples:
- `/transcript ~/Desktop`
- `Export this conversation transcript to ~/Desktop`

## Steps

1. Validate that the target directory exists.
2. Resolve the bundled script path:
   - Prefer `${CLAUDE_SKILL_DIR}/scripts/jsonl_to_md.py` when `CLAUDE_SKILL_DIR` is set.
   - Otherwise try `$HOME/.claude/skills/transcript/scripts/jsonl_to_md.py`.
   - If that does not exist, try `$HOME/.codex/skills/transcript/scripts/jsonl_to_md.py`.
3. Run:
   ```bash
   python3 "<script-path>" "<target-directory>"
   ```
4. Report the full path of the generated Markdown file.

The script picks the current session from the runtime it is running in. If discovery fails, convert the JSONL file directly:

```bash
python3 "<script-path>" "<session.jsonl>" "<output.md>"
```

## Where each runtime stores transcripts

### Cursor

Cursor writes the live Agent chat to disk as JSONL. That file is the source of truth. There is no documented, reliable "Export Chat" command that produces the same full transcript.

Path:

```text
~/.cursor/projects/<workspace-slug>/agent-transcripts/<chat-uuid>/<chat-uuid>.jsonl
```

- `<workspace-slug>` is the workspace path with leading `/` removed and remaining `/` replaced by `-`. Example: `/Users/corey` → `Users-corey`.
- The parent chat file is named `<uuid>/<uuid>.jsonl`. Ignore `subagents/` files unless the user asked for a subagent transcript.
- If the user names a chat UUID, use that file. Otherwise use the newest parent JSONL whose project slug matches the current workspace (or its parent workspace).
- When citing a Cursor chat, use `[short title](<uuid>)` without the `.jsonl` suffix.

If the user is in a side chat, the parent UUID is in the inherited context (`agent_id`). Export the parent file unless they asked for the side-chat file specifically.

### Claude Code

Claude sets `CLAUDE_SESSION_ID`. Sessions live at:

```text
~/.claude/projects/<project-slug>/<session-id>.jsonl
```

The script finds this from `CLAUDE_SESSION_ID`.

### Codex

Codex sets `CODEX_THREAD_ID`. Sessions live under:

```text
~/.codex/sessions/YYYY/MM/DD/*<thread-id>*.jsonl
```

The script finds this from `CODEX_THREAD_ID`.

## Notes

- The output filename is `transcript-<session-id>.md`.
- If session discovery fails, say which runtime was detected and which directory was searched.
- Do not dump the raw JSONL into chat. Convert it and give the Markdown path.
