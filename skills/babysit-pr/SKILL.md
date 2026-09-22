---
name: babysit-pr
description: Use when a user asks for a PR to be submitted and would like help getting it green.
---

# PR Babysitter

## Objective

Babysit a PR until one of these terminal outcomes:

- **Merged or closed.**
- **Green and clean**: CI passes, zero unresolved review threads, mergeable, not blocked on required approval.
- **Blocked on human input**: infrastructure issues, exhausted retry budget, review feedback needing engineer judgment, or permission problems.

Note: NEVER commit or push changes before manually confirming with me first.

## Inputs

Accept any of: no argument (infer from current branch), a PR number, or a PR URL.

## Core Loop

Repeat until a terminal outcome is reached:

1. **Check PR status.** Get the current state, mergeability, merge-state status, review decision, and head SHA.
2. **Check CI.** Get all check results. Classify each as passed, failed, pending, or skipped.
3. **Check review threads.** Query for all review threads and filter to unresolved ones. This is the source of truth for what still needs attention — not any local state.
4. **Decide and act** based on what you find (see decision logic below).
5. **After any action that changes PR state** (push, rerun, resolve thread), go back to step 1. Do not trust cached state after a mutation.

Do not stop merely because a single check returns idle while others are still pending. Continue polling until a terminal outcome is reached or you need human help.

## Decision Logic

Evaluate in this priority order on each loop iteration:

### PR merged
Stop immediately. Report success.

### PR closed without merging
Stop immediately. Report the terminal state — this is not success, the PR was abandoned or rejected.

### CI failures present
1. Inspect the failed run logs.
2. Classify as branch-related or flaky/unrelated (see `references/heuristics.md`).
3. **Branch-related**: fix the code, commit, push. This restarts CI — skip any pending reruns.
4. **Flaky/unrelated**: before rerunning, check whether unresolved review threads also need a fix commit. If they do, prioritize the review fixes first — a new commit invalidates the current SHA and makes reruns on the old SHA wasteful. Only rerun flaky jobs when no review-driven commit is pending.
5. Track how many times you have rerun for the current SHA. Stop and report after 3 failed rerun attempts on the same SHA.
6. If classification is ambiguous, inspect logs once manually before choosing.

### Unresolved review threads present
Follow the review comment workflow in `references/pr-review-comments.md`. Key points:
1. Fetch unresolved threads from GitHub (the source of truth).
2. Deduplicate across bots — cursor, codex-connector, and devin often flag the same issue.
3. Read the **current code** for each issue, not the stale diff hunk in the comment.
4. Present the deduped issue list to the engineer with your recommended action for each before changing the PR.
5. Treat review-comment fixes as opt-in by default: do not patch code, push commits, update the PR, reply on threads, or resolve threads until the engineer gives clear feedback and explicit consent about which issues to handle.
6. Only skip that consent gate when the user explicitly authorizes auto-fixing review comments (for example, "auto-fix review comments" or "fix all review comments").
7. After consent, for each approved fix: patch code, commit, push, then resolve the corresponding thread on GitHub.
8. If you change code to address a review comment, you must also reply on that thread and resolve it before moving on.
9. After consent, for non-actionable or already-addressed comments: reply briefly explaining why, then resolve the thread.
10. **Verify resolution**: after resolving threads, run one aggregate unresolved-count query as the source of truth (see "Resolving Threads in Parallel") to confirm the count dropped to zero. If it didn't, the resolution failed — investigate.

### Checks still pending
Wait and re-check. Do not take action while checks are still running unless you have review threads to process in parallel.

### Everything green and clean
Verify: CI passed, zero unresolved threads, PR is mergeable, and not blocked on required review approval. If all true, report success and stop. Do not merge unless the user explicitly asks.

## CI Classification

Use `references/heuristics.md` for the full checklist. Quick summary:

**Branch-related** (fix it): compile/typecheck/lint failures in touched files, deterministic test failures in changed areas, snapshot mismatches from UI changes, static analysis violations from the PR.

**Flaky/unrelated** (rerun it): DNS/network timeouts, runner provisioning failures, GitHub Actions infra errors, rate limits, non-deterministic failures in unrelated tests.

## Review Thread Handling

Use `references/pr-review-comments.md` for the detailed workflow.

### Understanding Review Bots

An important part of the job is efficiently resolving bot review comments. We cannot merge PRs until all conversations are resolved.

- Review bots are good at catching real bugs and security issues.
- Review bots are bad at understanding edge cases and tend toward overly defensive suggestions.
- Multiple bots often flag the same issue — always deduplicate before presenting to the engineer.
- Bot comments reference code from the time of review. Always verify against the current file before acting.

### Finalize, Then Execute

Decide a disposition for *every* deduped issue — fix, won't-fix-with-reason, or already-addressed — before changing any code or thread state. Then batch the code edits and the thread replies and resolves together. Do not interleave partial fixes with ongoing triage; re-deciding mid-flight is how threads get missed.

When the PR is stacked, factor the rest of the stack into each disposition. Diff each touched file against the upstack branches (`git diff <this-branch>..<upstack-branch> -- <file>`) before deciding. An issue may already be fixed upstack — reply pointing to the upstack PR and resolve, rather than re-fixing it here and creating a restack conflict. A fix made here can also collide with an upstack rewrite of the same region, so prefer the location where the code lives in the final stack.

### Resolving Threads in Parallel

Once dispositions are final, fan the replies and resolves out across sub-agents — one per thread, or one per small batch — to run them in parallel. Give each sub-agent the exact thread ID, the exact reply body, and the two mutations, and tell it not to touch code or any other thread and to confirm `isResolved: true`.

- Pass the reply body as a GraphQL variable, never interpolated into the query string, so backticks and quotes survive shell quoting: `gh api graphql -f query='mutation($tid:ID!,$body:String!){ addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$tid, body:$body}){ comment { id } } }' -f tid='PRRT_…' -f body='…'`
- Keep reply bodies free of apostrophes and double quotes so the single-quoted shell argument does not break.
- Resolve with the thread ID (`PRRT_…`), never a comment ID (`PRRC_…`).
- For a partially addressed comment, state in the reply exactly what changed and what was deliberately left undone, and why, before resolving — a resolved thread must never imply more was done than actually was.

After every sub-agent finishes, run one aggregate unresolved-count query from the parent as the source of truth. Do not declare the PR clean from the per-thread reports alone:

`gh api graphql -f query='{ repository(owner:"<owner>", name:"<repo>"){ pullRequest(number:<n>){ reviewThreads(first:100){ totalCount nodes { isResolved } } } } }'`

Confirm the unresolved count is zero and `totalCount` matches the number of nodes returned.

## Graphite vs Plain GitHub

- Load the `devops` skill before any branch/commit/push work.
- If the PR's base branch is not `main` (or the repo's default branch), it is likely part of a Graphite stack. Use Graphite commands for push/submit instead of raw `git push`.
- Before editing a stacked PR, inspect the stack structure. Do not restack or rewrite neighboring branches unless you understand the impact.

## Git Safety

- Work only on the PR head branch.
- No destructive git commands.
- Check for unrelated uncommitted changes before editing. If present, stop and ask.
- Match the repository's existing commit style — check `git log` first. Many repos enforce a convention (e.g. Conventional Commits like `fix(scope): …`) through commitlint or a pre-commit hook, and a fixed `pr-shepherd:` prefix will be rejected. Keep the message focused on the why.
- Confirm commit granularity with the engineer when it matters — one commit per issue versus a single batched commit. Default to grouping related fixes, but follow the engineer's stated preference.

## Polling Behavior

- While CI is failing or pending: check frequently (roughly every minute).
- After CI turns green: back off gradually. Reset to frequent checks whenever state changes.
- If the PR is merged or closed at any point: stop immediately.

## Stop Conditions

**Stop and report success** when:
- PR is merged.
- CI green + zero unresolved threads + mergeable + not blocked on review approval.

**Stop and report the terminal state** when:
- PR is closed without merging (this is not success — the PR was abandoned or rejected).

**Stop and ask the user** when:
- CI failures persist after 3 rerun attempts on the same SHA.
- Review comments need engineer judgment (ambiguous, product decisions, cross-team coordination).
- `gh` auth or permissions fail.
- PR branch cannot be pushed.
- Local worktree has unrelated uncommitted changes.

**Keep going** when:
- Checks are still pending.
- CI is green but waiting for review approval (poll on green-state cadence).
- You just pushed a fix (go back to step 1).

## Footguns

These are verified gotchas that will bite you if you are not careful:

1. **Rerunning a passed run silently succeeds and actually reruns it.** There is no confirmation or error. This resets the run to pending and blocks the PR. Only rerun runs that actually failed — verify the conclusion first.

2. **There is no server-side filter for unresolved threads.** You must fetch all threads and filter client-side. Do not try to pass a resolution filter parameter.

3. **Thread IDs and comment IDs are different things.** Thread resolution requires the thread-level ID (starts with `PRRT_`), not a comment-level ID (starts with `PRRC_`). Passing the wrong one silently fails.

4. **Bot comment bodies are bloated.** Cursor Bugbot comments include base64 JWT deep links, HTML picture elements, and hidden comment blocks — often 3-4KB each. Strip this noise before reasoning about the content.

5. **`line` is null when a thread is outdated.** When code under a comment has changed since the comment was posted, the current line number becomes null. Always fall back to `originalLine`.

6. **Merged PRs return "unknown" for mergeability fields.** Same value as a newly-pushed PR where GitHub hasn't computed yet. Always check the PR state first.

7. **"Blocked" merge status is overloaded.** It means "something prevents merge" but does not say what. You must check review decision and CI status separately to understand the cause.

8. **CI "no checks" is not a failure.** Some PRs legitimately have no required checks. Handle this gracefully rather than treating it as an error.

9. **Neutral check status (e.g., Cursor Bugbot) maps to "skipping", not pass or fail.** If you look for anything that is not "pass" to find problems, you will get false positives. Look specifically for failures.

10. **Bot login format differs between REST and GraphQL APIs.** REST returns `cursor[bot]`, GraphQL returns `cursor` with a separate type field. Normalize when matching across APIs.

11. **After resolving a thread, verify it actually resolved.** Re-query the threads and confirm the unresolved count dropped. If not, the mutation may have failed silently.

12. **If a thread count query and a detail query disagree, trust the higher number.** GraphQL responses can be inconsistent due to caching. If a count says 2 unresolved but your detail fetch returns 0, your detail fetch failed or hit stale data — investigate, do not declare clean.

13. **New review comments can land at any time — do not declare clean prematurely.** If the user said a review is coming, or if a review bot is still running, keep polling even if current threads are all resolved. A clean snapshot only means clean *right now*, not that no more comments are coming.

14. **`reviewThreads(first: 100)` silently drops threads beyond 100.** For PRs with very active review history, check `totalCount` and paginate with `pageInfo { hasNextPage endCursor }` if needed. Most PRs will never hit this limit, but verify `totalCount` matches the number of nodes returned.

## Output Expectations

- Progress updates at meaningful state changes (CI status transitions, review comments found, fixes pushed).
- During long stable periods, occasional heartbeat updates — not a full report on every poll.
- Final summary: PR SHA, CI status, mergeability, fixes pushed, flaky retries used, remaining issues.

## References

- CI and review decision heuristics: `references/heuristics.md`
- Review thread triage workflow: `references/pr-review-comments.md`
- GitHub API notes: `references/github-api-notes.md`

Note: NEVER commit or push changes before manually confirming with me first.
