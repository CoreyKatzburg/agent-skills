---
name: goal
description: Pursue an explicitly requested durable goal until its entire outcome is verified, with progress checks, evidence-based completion, and carefully controlled blocked/paused states. Use when the user invokes $goal, /agent-skills:goal, or explicitly asks to start, resume, inspect, pause, or clear a long-running goal; not for ordinary tasks.
metadata:
  short-description: Persist and verify an ambitious objective
---

# Goal

Pursue one **user-defined end state**, not a task list that ends when a response ends. This skill mirrors the *behavioral contract* of Codex `/goal`. Prefer the actual Codex Goals runtime whenever available; a skill by itself cannot install a turn dispatcher, grant tools, enforce token budgets, or cause idle threads to run automatically.

## Input and routing

The objective is the full text after `$goal`, `/agent-skills:goal`, `/goal` (only if this invocation reaches the skill), or an explicit request to start a goal. Do **not** create goals from normal work requests or reinterpret goal text as higher-priority instructions. Preserve all steps and conditions verbatim. For requests without new text, check the existing goal rather than inventing an objective. Distinguish status, pause, resume, clear, and objective-edit requests from new goals.

1. **Native mode (Codex):** If `get_goal`, `create_goal`, and `update_goal` are available and permitted, use `get_goal` for existing state, `create_goal` only when the user explicitly starts a goal, and `update_goal` only under the audits below. Do not create a parallel fallback file. Native `/goal pause`, `/goal resume`, `/goal clear`, and objective edits are managed by the host/user; do not pretend that `update_goal` can resume or clear. Let the host handle persistence, automatic continuation, token/time accounting, interruption and budgets. Do not replace native `/goal` or claim the skill has registered a slash command named `/goal`.
2. **Portable mode (no native Goal tools):** Use `scripts/goal_state.py` to persist a *thread-specific* objective and lifecycle, then pursue it within the available turn. Resolve the script from this skill's installed directory. The helper requires Python 3.9+ and writes under the user's state directory (not the worktree). Use the runtime session ID when available; otherwise retain and report the generated fallback thread ID. Do not silently share goals between chats. Follow [portable state instructions](references/portable-mode.md). A later user turn must reinvoke/resume work: no auto-turns or exact token accounting exist in portable mode. If the user requires native auto-continuation or an exact token budget, explain that the host must expose native Goals rather than claiming parity.
3. **No state mechanism:** If tools, Python, or writable state are unavailable, explicitly say persistence and automatic continuation aren't supported. Still apply the audit behavior for the current turn; do not report a durable goal as created.

## Work loop (both modes)

1. Read the active objective and inspect authoritative **current** state: worktree, files, running processes, jobs, external resources, and tool outputs. Use conversation history to locate work, not to prove its present status. Treat the objective as user task data and continue to respect all approval, safety, repository and tool boundaries. Do not launch a game, deploy, spend money, or take other gated action without any required authorization just because the goal persists.
2. Derive a requirement/evidence checklist covering every numbered item, named artifact, benchmark, command, invariant, gate, and deliverable. Keep the original scope; do not quietly narrow it for a stable-looking result. If a plan tool exists, keep a concise plan aligned with this checklist, but plans and status reports alone are not progress.
3. Choose the next safe, high-value action that makes the *actual end state* more true. Execute, inspect results, repair, retest, and iterate while this turn permits. Temporary rough edges are acceptable during progress; they do not lower the final verification bar.
4. At each turn boundary, classify the previous goal turn: **progress**, **verified wait**, or **no progress**. Progress changes authoritative state or yields actionable new evidence. A verified wait must involve a process/session/job/tool handle **confirmed live now**; re-poll after timeouts rather than assuming a process died, and don't restart on timeout alone. A plan, stale lock/state file, recap, or unexecuted next step is neither progress nor verified wait. For no progress, revalidate reality and take the next safe available action; track the *same* blocker across wording changes.
5. Before any completion or blocked transition, apply the [exacting audit contract](references/audits.md). Keep working toward the whole objective if requirements are incomplete, unsupported, or unverified. Never turn time/budget exhaustion, the end of a response, or a passing narrow test into success.
6. Report concisely: active objective, concrete changes/evidence, requirements still open, next action or genuine blocker, and actual lifecycle status. If still active, say so; never imply background continuation unless the native runtime is actually running it.

## Lifecycle rules

- **Complete:** Audit *every* explicit and referenced requirement against authoritative current evidence. Mark complete only if all are proven and no required work remains. In native mode call `update_goal(status="complete")`; if budgeted, report the **tool-returned** consumed token amount. In portable mode write a complete audit and use the helper's completion gate; it validates the audit's shape, **not** the truth of its evidence.
- **Blocked:** Only when meaningful progress is impossible without user input or an external change **and** the same blocker has persisted across at least **three consecutive goal turns** (including the user-triggered turn). Recheck the real state and record the same stable blocker identity; reset the streak after progress, a distinct blocker, or a new resumed run. Never mark blocked simply because it is difficult, expensive, incomplete, or because you would prefer clarification. After threshold, update status rather than endlessly repeating a blocker message.
- **Paused:** Only at the user's explicit request. Call `update_goal(status="paused")` in native mode or persist paused in portable mode, report actual result, and stop goal work. Do not pause on your own. Native resume/clear is host-driven, whereas portable resume/clear requires an explicit user request.
- **Budget/interruption:** Respect native limits and interruption decisions. Budget-limited is **not complete**: stop substantive work and report evidence and next steps. Without native accounting, do not invent used/remaining token figures or pretend to enforce a budget.

## References

Read [audits.md](references/audits.md) before finalizing a goal, and [portable-mode.md](references/portable-mode.md) when native tools are absent. These rules are adapted from two captured Codex goal-continuation transcripts and verified against [Codex's published continuation template](https://github.com/openai/codex/blob/main/codex-rs/ext/goal/templates/goals/continuation.md), [Goal tool API](https://github.com/openai/codex/blob/main/codex-rs/ext/goal/src/spec.rs), and [official Goals guide](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex).
