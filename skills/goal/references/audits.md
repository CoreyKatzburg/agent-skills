# Goal audits (read before any terminal status)

These checks preserve the strict completion/blocked behavior in the Codex continuation transcripts and in the [upstream prompt](https://github.com/openai/codex/blob/main/codex-rs/ext/goal/templates/goals/continuation.md).

## Completion: proof, not absence of red flags

Assume **not complete** until proven otherwise. Derive acceptance criteria from the original objective **plus** referenced plans, files, specifications, issues, and user instructions. For every item identify the source capable of proving its current state: code and tests, command output, actual benchmark measurements, running application, PR status, rendered asset, or another authoritative source.

For each requirement record:

| Field | Meaning |
| --- | --- |
| `requirement` | Original artifact, behavior, constraint, test, gate, or deliverable (never a narrower substitute) |
| `status` | Proven, contradicted, incomplete, weak/indirect evidence, or missing |
| `source` | Exact current-state file, command, process, output, URL, or handle inspected |
| `evidence` | What the source shows, including measured values/results where applicable |

A test result proves only what its actual coverage demonstrates. A manifest or green CI does not substitute for runtime verification if runtime behavior was requested. Partial implementation, previous chat assertions, intent, and plausible results are **not proof**. Compare the scope of each claim with the observed evidence. Continue if **any** requirement is not proven. If all are proven, native `update_goal(status="complete")` or portable `status complete --audit ...` is allowed.

Example portable audit JSON (only *after* real verification; add **all** requirements):

~~~json
{
  "requirements": [
    {"requirement": "Test passes", "status": "proven", "source": "pytest -q at commit abc123", "evidence": "37 passed, 0 failed"},
    {"requirement": "Requested artifact published", "status": "proven", "source": "PR #42 Files changed at commit abc123", "evidence": "Artifact exists in requested path"}
  ]
}
~~~

The helper only checks that each entry says `proven` and includes fields. **The agent must actually inspect every source, verify requirement coverage, and avoid manufacturing evidence.**

## Blocked audit

Blocked requires both (a) no available meaningful safe action without user input or external state change and (b) at least three **consecutive goal turns** with the same real blocker. The originating user-triggered goal turn counts. Revalidate each time, attempt other safe meaningful actions if possible, and identify equivalent blockers by actual cause rather than changing descriptions. No-progress turns with distinct blockers do not count together. A verified live wait is not a blocker. After a blocked goal resumes on user instruction, start a fresh streak.

## Wait/no-progress classification

- `progress`: authoritative state changed or newly observed evidence changes the next action.
- `verified-wait`: poll a specific currently live process/session/job/tool handle. A timeout in observing it doesn't prove termination; re-poll/inspect state.
- `no-progress`: an unexecuted plan, recap, stale lock, status restatement, or unchanged evidence. Reinspect current state and act if an option exists.

Do not call lifecycle update functions on ordinary active turns. Do not invent an accounting figure for a portable goal.
