# GitHub API Notes

Quick reference for the key GitHub API operations used during PR babysitting. The agent should use the `gh` CLI directly for all of these — no intermediary scripts.

## PR Status

Get current PR state, mergeability, review decision, and head SHA via `gh pr view` with JSON output.

Key fields and their quirks:
- `mergeable`: string, not boolean. Values: `MERGEABLE`, `CONFLICTING`, `UNKNOWN`.
- `mergeStateStatus`: values include `CLEAN`, `BLOCKED`, `DIRTY`, `UNSTABLE`, `UNKNOWN`. `BLOCKED` is overloaded — does not tell you why.
- `reviewDecision`: `APPROVED`, `REVIEW_REQUIRED`, `CHANGES_REQUESTED`, or empty string (ambiguous — could mean no review rules or no reviews yet).
- Merged PRs return `UNKNOWN` for both `mergeable` and `mergeStateStatus`. Always check `state` first.

## CI Checks

Get check results via `gh pr checks` with JSON output.

Key fields:
- `bucket`: `pass`, `fail`, `pending`, `skipping`. Note: `NEUTRAL` status (e.g., Cursor Bugbot) maps to `skipping`, not `pass`.
- `state`: `SUCCESS`, `FAILURE`, `IN_PROGRESS`, `SKIPPED`, `NEUTRAL`. No separate `QUEUED` state — everything pending is `IN_PROGRESS`.

Exit codes: 0 = all pass, 1 = any failed OR no checks exist, 8 = checks pending. Exit code 1 has dual meaning — handle "no checks" gracefully.

The `--required` flag filters to only branch-protection-required checks — useful for determining actual merge readiness.

## Failed Run Inspection

Get workflow runs for a SHA via the GitHub Actions API. Filter for failed conclusions.

Inspect failure logs with `gh run view <run-id> --log-failed`. Output is tab-separated (`job-name\tstep-name\tlog-line`). Can be noisy with runner bootstrap lines.

## Rerunning Failed Jobs

Use `gh run rerun <run-id> --failed` to rerun only failed jobs.

**Critical**: this command succeeds silently even on already-passed runs, actually re-triggering them. Always verify the run actually failed before calling rerun.

## Review Threads (GraphQL)

Use the GraphQL API for review threads. The REST API has no concept of thread resolution.

Key points:
- `reviewThreads` on a pull request returns all threads. There is no server-side `isResolved` filter — fetch all and filter client-side.
- Thread IDs have prefix `PRRT_`. Comment IDs have prefix `PRRC_`. Do not mix them.
- `line` is null when a thread is outdated (code changed since comment). Use `originalLine` as fallback.
- `isOutdated` indicates whether the code under the comment has changed.
- `viewerCanResolve` is a useful pre-flight check before attempting resolution.
- `resolvedBy` returns who resolved the thread — can be a bot.

## Thread Mutations (GraphQL)

- **Resolve**: `resolveReviewThread(input: {threadId: "PRRT_..."})` — returns `thread { isResolved }`.
- **Unresolve**: `unresolveReviewThread(input: {threadId: "PRRT_..."})` — same structure.
- **Reply**: `addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: "PRRT_...", body: "..."})` — adds a comment to an existing thread.

## Bot Author Gotchas

- GraphQL returns bot logins without `[bot]` suffix (e.g., `cursor`) with `__typename: "Bot"`.
- REST returns bot logins with `[bot]` suffix (e.g., `cursor[bot]`) with `type: "Bot"`.
- Normalize when matching across APIs.
- `author_association` is unreliable for bot detection — bots get `NONE`, same as external humans.

## General PR Comments

Use `gh pr comment <number> --body "..."` for general timeline comments (not inline on code).
