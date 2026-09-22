# CI / Review Heuristics

## CI classification checklist

Treat as **branch-related** when logs clearly indicate a regression caused by the PR branch:

- Compile/typecheck/lint failures in files or modules touched by the branch
- Deterministic unit/integration test failures in changed areas
- Snapshot output changes caused by UI/text changes in the branch
- Static analysis violations introduced by the latest push
- Build script/config changes in the PR causing a deterministic failure

Treat as **likely flaky or unrelated** when evidence points to transient or external issues:

- DNS/network/registry timeout errors while fetching dependencies
- Runner image provisioning or startup failures
- GitHub Actions infrastructure/service outages
- Cloud/service rate limits or transient API outages
- Non-deterministic failures in unrelated integration tests with known flake patterns

If uncertain, inspect failed logs once before choosing rerun.

## Decision tree (fix vs rerun vs stop)

1. If PR is merged/closed: stop.
2. If there are failed checks:
   - Diagnose first.
   - If branch-related: fix locally, commit, and update the PR branch with the transport that matches the workflow (`git push` or Graphite submit).
   - If likely flaky/unrelated and all checks for the current SHA are terminal: rerun failed jobs.
   - If checks are still pending: wait.
3. If flaky reruns for the same SHA reach the retry limit (default 3): stop and report persistent failure.
4. Independently, check for unresolved review threads, dedupe them into unique issues, and ask the engineer which issues to handle unless the user explicitly told you to auto-fix review comments.

## Review comment agreement criteria

Address the comment when:

- The comment is technically correct.
- The change is actionable in the current branch.
- The requested change does not conflict with the user's intent or recent guidance.
- The change can be made safely without unrelated refactors.

Apply this triage policy:

- Prioritize bug, security, and correctness comments.
- Do not auto-accept defensive or speculative edge-case expansion unless the contract actually requires it.
- If multiple review agents flag the same concrete issue, treat it as higher-signal and investigate first.
- Do not auto-fix new review comments by default; present the deduped issue list, include your recommended action for each issue, and wait for explicit engineer consent before changing code. Only skip that gate when the user clearly asked you to auto-fix review comments.
- Batch worthwhile selected review-agent fixes into one commit, then continue the babysitting loop.
- For non-actionable review-agent comments, wait for the engineer to approve that disposition before replying or resolving the thread unless the user explicitly told you to auto-fix review comments.

Do not auto-fix when:

- The comment is ambiguous and needs clarification.
- The request conflicts with explicit user instructions.
- The proposed change requires product/design decisions the user has not made.
- The codebase is in a dirty/unrelated state that makes safe editing uncertain.

### Understanding Review Agents

Claude, Devin, and Cursor all agents that respond to comments.

An important part of your job, and one of the most useful, is resolving comments from code review agents. We cannot merge PRs until all conversations are resolved.

You are most effective when you properly distinguish which code review agent comments need to be fixed and which ones do not. In addition to the above, use these guiding principles for understanding coding agent responses:

- Review agents do not have enough context to understand what edge cases do or do not apply.
- Review agents use overly defensive programming and will often instruct you to add more edge cases.
- Review agents do have a good understanding of bugs and security practices.

## Stop-and-ask conditions

Stop and ask the user instead of continuing automatically when:

- The local worktree has unrelated uncommitted changes.
- `gh` auth/permissions fail.
- The PR branch cannot be pushed.
- CI failures persist after the flaky retry budget.
- New review comments are present and the user has not already told you which issues to handle or explicitly authorized auto-fixing review comments.
- Reviewer feedback requires a product decision or cross-team coordination.
