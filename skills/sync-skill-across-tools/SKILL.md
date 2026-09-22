---
name: sync-skill-across-tools
description: Convert a skill or a Cursor/Claude command into one canonical Codex skill and symlink it into Claude and Cursor so it is available from all three tools.
metadata:
  short-description: Make one skill available across Codex, Claude, and Cursor
---

# Sync Skill Across Tools

Take an existing skill or command and make it available from all three coding tools (Claude Code, Codex, Cursor) as a single canonical skill with symlinks — so there is exactly one file to edit.

## The layout this produces

- **Canonical (the one real copy):** `~/.codex/skills/<name>/SKILL.md`
- **Claude:** `~/.claude/skills/<name>` → symlink → the Codex folder
- **Cursor:** `~/.cursor/skills/<name>` → symlink → the Codex folder

Codex reads its own folder natively; Claude and Cursor just point at it. Editing the Codex file updates all three at once.

## Steps

Substitute the skill's kebab-case name for `<name>` throughout.

1. **Find every existing copy.** Commands and skills live in different dirs, so check all of them:

   ```bash
   find ~/.codex ~/.claude ~/.cursor -maxdepth 3 -iname "*<name>*"
   ```

   Also read the source file so you can reuse its content. Command files live in `~/.claude/commands/` and `~/.cursor/commands/`; skills live in `~/.codex/skills/`, `~/.claude/skills/`, `~/.cursor/skills/`. If a copy is already a symlink into `~/.codex/skills/`, that part is already done.

2. **Create the canonical skill** at `~/.codex/skills/<name>/SKILL.md` with this frontmatter, then the original body verbatim:

   ```markdown
   ---
   name: <name>
   description: <one sentence — what it does and when to use it>
   metadata:
     short-description: <short label>
   ---

   <original command/skill body, unchanged>
   ```

   The frontmatter is what makes Claude and Codex discover it — a bare command file lacks it. Keep `description` to one sentence.

3. **Remove the old command files** (they are replaced by the skill):

   ```bash
   rm ~/.claude/commands/<name>.md ~/.cursor/commands/<name>.md
   ```

   Only remove the ones that exist — one tool may not have a copy.

4. **Symlink the skill into Claude and Cursor:**

   ```bash
   ln -s ~/.codex/skills/<name> ~/.claude/skills/<name>
   ln -s ~/.codex/skills/<name> ~/.cursor/skills/<name>
   ```

5. **Verify** the symlinks resolve and read through to the canonical file:

   ```bash
   ls -la ~/.claude/skills/<name> ~/.cursor/skills/<name>
   cat ~/.claude/skills/<name>/SKILL.md >/dev/null && echo "claude reads ok"
   cat ~/.cursor/skills/<name>/SKILL.md >/dev/null && echo "cursor reads ok"
   ```

## Notes

- The `rm` and `ln` commands write outside the working directory, so a sandbox may block them with "Operation not permitted" — rerun those with the sandbox disabled.
- Each app may cache its skill list; reload the app if a newly synced skill doesn't appear.
- This is a destructive-ish move (deleting the old command). Confirm with the user before running if they haven't already approved this exact process.
