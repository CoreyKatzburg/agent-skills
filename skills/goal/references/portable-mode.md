# Portable fallback (no native Codex Goal tools)

Use only when `get_goal` / `create_goal` / `update_goal` aren't available. This is *persistence and lifecycle bookkeeping*, **not** automatic continuation. Host skills cannot dispatch additional turns from an idle thread or consume native thread-budget telemetry. Do not install a background process or pretend that one exists.

Run `python3 <installed-skill-dir>/scripts/goal_state.py ...` (Windows: `python`). The helper stores state at `AGENT_SKILLS_GOAL_STATE_DIR`, or `XDG_STATE_HOME/agent-skills/goals`, or a user-local OS-specific state directory. It hashes IDs to filenames to prevent path escapes. State is personal to the machine and **not** synchronized across hosts. It does not write to the project repository.

The helper resolves identity from `--thread-id`, `AGENT_SKILLS_GOAL_THREAD_ID`, `CODEX_THREAD_ID`, or `CLAUDE_SESSION_ID`. **Do not** default to a repository path, since parallel chats in the same repository must not overwrite each other's goals. When no session ID is available, `create` generates a `portable-<UUID>` ID; record that ID in the chat for later commands. For later invocations supply `--thread-id <that-id>` or set the environment variable. Never guess the ID.

## Commands

Commands below omit `--thread-id <id>` for readability. Add it whenever the session environment cannot identify the thread. The flag goes **before** the subcommand.

- Start after explicit invocation: `python goal_state.py create --objective "<complete original objective>"`. Reject a second goal while one is unfinished; do not overwrite an objective. If the goal is edited, the user must explicitly replace/clear it first in fallback mode; prefer native editing where supported.
- Inspect at the beginning of each continued turn: `python goal_state.py show`.
- Record **one** turn outcome at the end of each goal turn: `python goal_state.py checkpoint --turn-id "<actual unique turn label>" --kind progress --evidence "<verified changed state>"`. Use `--kind no-progress --blocker "<stable cause>" --evidence "<current check>"` for a genuine impasse; use `--kind verified-wait --handle "<confirmed live handle>" --evidence "<poll result>"` for an actual wait. The script rejects duplicate turn IDs. Do not count a separate tool call or retry inside the same turn as a separate goal turn.
- Block only after the third consecutive recorded no-progress turn for the same blocker *and* the blocked audit: `python goal_state.py status blocked`.
- Complete only after every original requirement is proven: write an audit JSON with **all** requirements and source evidence per `audits.md`, then `python goal_state.py status complete --audit /path/to/audit.json`.
- Pause only at user request: `python goal_state.py status paused --user-requested`; resume paused/blocked after user request with `python goal_state.py status active --user-requested` (resets the blocked streak).
- Clear only at user request: `python goal_state.py clear --user-requested`.

The script validates state transitions and minimum audit structure; the agent remains responsible for validating actual evidence. It is **not** a background job runner, scheduler, authorization system, or exact token meter. If the user explicitly requires a token budget, recommend native Codex Goals rather than silently claiming a limit is enforced.

For the actual Codex `/goal` feature, use the host command and feature flag described in the [official guide](https://learn.chatgpt.com/use-cases/follow-goals). A user may enable it via `codex features enable goals` where supported. This skill does not replace that command or its dispatcher.
