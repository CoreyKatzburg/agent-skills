---
name: cross-provider-code-review
description: Run and actively supervise a resumable code review with a user-selected Anthropic model through Claude Code or OpenAI model through Codex, safely handle tool requests, debate unclear findings, and independently triage the final comments. Use when the user invokes /cross-provider-code-review or asks Claude, Codex, or Cursor to obtain and assess a review from a chosen model provider.
---

# Cross-provider code review

Start a fresh reviewer session with the selected provider, supervise it until the review is complete, and independently investigate its comments. Keep the workflow read-only unless the user separately authorizes implementation.

## 1. Collect the review inputs

Always ask which model and reasoning effort should perform the review. Ask both in one message and wait for the answer. Do not choose a model. If the user omits effort, use `high` and state that default before launching.

Resolve the effort value at runtime instead of maintaining a fixed cross-provider alias map:

- If the user supplies an exact effort identifier, preserve it unless the selected provider or model rejects it.
- If the user uses an informal term such as `extra`, `extra high`, `maximum`, or `deepest`, inspect the installed provider CLI's current help, model metadata, model picker, or current first-party documentation to find the exact effort identifier accepted by that provider and model.
- If there is exactly one clear match, state the resolved identifier before launching. If the match is ambiguous or cannot be verified, show the currently advertised choices and ask the user which one to use.
- Re-resolve informal effort terms on every invocation because provider names and supported levels may change. Never assume that one provider's current name applies to another provider or a future model.
- Let the provider CLI perform final validation. If it rejects the effort, show the error and ask for another level; never silently fall back.

Use the current Git checkout when already inside a repository. Otherwise ask which repository or worktree to review, then resolve and state its repository root. Do not review a different checkout merely because it has a similar branch name.

Route the model by provider:

- Anthropic names such as `claude`, `fable`, `opus`, `sonnet`, or `haiku` use Claude Code.
- OpenAI names such as `gpt-*`, `codex-*`, or `o*` use Codex.
- Apply the same family-based rule to future model versions, such as a future `gpt-5.7-*`; do not maintain a fixed version allowlist.
- If the name is ambiguous, ask whether it is an Anthropic or OpenAI model. Never guess the provider.

Preserve a canonical model ID exactly when supplied. Normalize an obvious informal OpenAI name such as `gpt 5.6 sol` to `gpt-5.6-sol`, tell the user what will be passed to the CLI, and let the CLI validate availability. If the CLI rejects the model, show the error and ask for another model; never silently fall back.

Read `/Users/corey/.agents/skills/code-review/SKILL.md` completely. Resolve its prerequisites before launching the reviewer:

1. Obtain the fixed comparison point if the user did not provide one.
2. Confirm the ref resolves and that the three-dot diff is non-empty.
3. Resolve the spec source and repository standards as directed by `code-review`.
4. If there is no spec, get the user's confirmation and record `no spec available`.

If `code-review` refers to a missing setup skill or issue-tracker guide, do not install or configure anything during this review. Use an available spec source or ask the user for the spec instead.

Pass the fixed point, commit list, spec content or path, and standards paths to the reviewer so the child session does not stop for missing context.

## 2. Build the reviewer prompt

Create temporary prompt and output files outside the repository when practical. Tell the reviewer to:

- Read and follow `$code-review` at `/Users/corey/.agents/skills/code-review/SKILL.md`.
- Review the supplied fixed-point-to-`HEAD` diff using both Standards and Spec axes.
- Use the supplied fixed point, commit list, standards sources, and spec context.
- Remain read-only: do not edit files, commit, push, post comments, or change remote state.
- Return actionable findings with severity and exact file/line evidence, and say explicitly when an axis has no findings.
- If blocked on a tool, state the exact tool call or command, why it is necessary, and the minimum requested scope. Do not substitute a more privileged action.
- Not invoke Claude Code, Codex, `/cross-provider-code-review`, or another external reviewer.

The reviewer may use native subagents because `$code-review` requires them, but every reviewer and subagent must remain read-only.

## 3. Start a resumable reviewer session

Run from the repository root. Use the exact selected model and normalized effort. Do not use ephemeral or no-persistence options because follow-up discussion must resume the same reviewer context.

Run every provider review-session launch and resume through the implementing agent's unsandboxed terminal execution boundary. If the host requires approval to leave its sandbox, request approval before launch. Explain that the provider CLI needs write access to its normal session store, such as `~/.claude` or `~/.codex`, so the session can be resumed.

The outer terminal escalation must not expand the reviewer's permissions. Keep the provider CLI's read-only sandbox, narrow allowed-tool rules, and approval settings unchanged.

Do not fall back to launching the reviewer inside the implementing agent's filesystem sandbox. If unsandboxed execution is unavailable or the user denies approval, stop and report that a resumable review cannot be launched.

### Anthropic model

Invoke Claude Code non-interactively with structured streaming output:

```bash
claude -p \
  --model "<anthropic-model>" \
  --effort "<effort>" \
  --permission-mode dontAsk \
  --allowedTools "Read,Glob,Grep,Agent,Bash(git status *),Bash(git diff *),Bash(git log *),Bash(git rev-parse *)" \
  --output-format stream-json \
  --verbose \
  "<reviewer-prompt>"
```

Capture the `session_id` from the stream and retain the complete JSONL transcript. `dontAsk` intentionally converts unapproved calls into observable denials instead of leaving a headless process waiting for an invisible prompt. Never use `--dangerously-skip-permissions`.

Verify that the provider persisted the session before describing it as resumable. Prefer checking the provider's local session registry. For Claude Code, confirm that a file matching the session ID exists under `~/.claude/projects`. When no stable registry check is available, use a minimal resume probe. If verification fails, retain the transcript and either relaunch through the correct terminal boundary or report the blocker.

### OpenAI model

Invoke Codex non-interactively with structured events and a persisted session:

```bash
codex exec \
  --model "<openai-model>" \
  --sandbox read-only \
  --config 'approval_policy="never"' \
  --config 'model_reasoning_effort="<effort>"' \
  --json \
  --output-last-message "<temporary-output-file>" \
  -
```

Send the reviewer prompt through stdin, capture the session ID from the JSONL events, and retain the complete event stream. `approval_policy="never"` makes an action outside the read-only sandbox fail visibly instead of waiting for an approval that `codex exec` cannot surface. Never use `--dangerously-bypass-approvals-and-sandbox`.

## 4. Monitor tool requests and prevent stalls

Continuously monitor the live process rather than waiting blindly for a final file:

1. Poll a yielded process or session frequently enough to surface progress and approval problems; do not leave it unchecked for more than about 30 seconds while it is active.
2. Inspect structured tool events, permission denials, sandbox failures, stderr, and the latest reviewer text.
3. If the process is alive but stops producing output, check whether it requested a tool, hit a permission boundary, exhausted turns, lost authentication, or is waiting for input.
4. Do not treat ordinary model reasoning or a long subagent review as a hang. Continue waiting when there is progress and no blocked request.
5. Do not finish the workflow while a reasonable tool request, clarification, or reviewer follow-up is unresolved.

Headless reviewer sessions cannot reliably show an interactive approval dialog. Handle a blocked request through the implementing agent's own approval boundary:

- Approve only a narrow, read-only request that is necessary for the review and clearly within the user's scope. Examples include reading files, `git diff`, `git show`, `gh pr view`, `gh pr diff`, or reading CI/check status.
- Prefer executing the exact safe command with the implementing agent's tool layer, then send the output back to the reviewer. This avoids broadly expanding the child agent's permissions.
- If the reviewer truly needs to run an approved command itself, resume it with only the exact temporary allow rule required; never grant unrestricted Bash, network, filesystem write, or broad provider access.
- Reject destructive or state-changing requests such as committing, pushing, force-pushing, merging, posting PR comments, changing branches, deleting files, deploying, changing permissions, or accessing unrelated secrets. Tell the reviewer why and ask for a read-only alternative.
- Automatically approve or proxy a reasonable request only when the implementing agent is confident about the command's full behavior, scope, and side effects.
- If a request appears reasonable but the implementing agent is not confident whether it is safe to approve, ask the user directly instead of guessing. Include the exact command or tool call, why the reviewer wants it, the uncertain risk, and a recommended approve-or-reject choice.
- Ask the user directly before any ambiguous, sensitive, externally visible, or state-changing request that might be justified. Do not proceed until the user explicitly approves it.

Record each approval, rejection, and proxied command for the final report.

## 5. Resume and converse with the reviewer

Use the captured session ID for all follow-ups. Never use `--last`, because another session may have started concurrently.

Run every follow-up resume command through the same unsandboxed terminal execution boundary used for the initial launch.

For Claude Code, resume with:

```bash
claude -p \
  --resume "<claude-session-id>" \
  --model "<anthropic-model>" \
  --effort "<effort>" \
  --permission-mode dontAsk \
  --allowedTools "<same narrow rules plus any exact temporary approval>" \
  --output-format stream-json \
  --verbose \
  "<follow-up>"
```

For Codex, resume with:

```bash
codex exec resume \
  --model "<openai-model>" \
  --config 'sandbox_mode="read-only"' \
  --config 'approval_policy="never"' \
  --config 'model_reasoning_effort="<effort>"' \
  --json \
  --output-last-message "<temporary-output-file>" \
  "<codex-session-id>" \
  -
```

Send safe tool output, a denial explanation, or a clarification prompt through the resumed session. Preserve the same model, effort, review target, and read-only boundary.

Converse with the reviewer when a finding is vague, lacks evidence, conflicts with the spec, or appears wrong. Ask it to defend the exact failure path, respond with contrary code or test evidence, and request a revised or withdrawn finding. Debate the evidence rather than deferring to the reviewer. Usually stop after three focused follow-up rounds per disputed finding; if it remains genuinely unresolved, report the disagreement or ask the user for missing domain context instead of looping indefinitely.

## 6. Triage the stabilized comments

After the reviewer finishes and material disputes are clarified, read its complete final position. Then read and follow `/Users/corey/.codex/skills/address-pr-comments/SKILL.md` completely, with these source adaptations:

- Treat the reviewer's stabilized findings as the comment set.
- Do not call `gh` to fetch comments unless the user separately asked to inspect an actual PR's open comments. Read-only `gh` calls needed to investigate a cited PR are allowed through the approval process above.
- For each actionable finding, use a capable native subagent to inspect the cited code, surrounding call path, tests, spec, and standards. Give each subagent one finding and the review target. Keep this investigation read-only.
- Prefer the most capable native subagent model available to the implementing provider; do not launch a new external reviewer session.
- If a subagent disputes a finding and the evidence is not decisive, resume the existing reviewer session and debate that evidence before classifying it.
- Classify each finding as valid, invalid, or needs user context. Do not assume the reviewer is correct.
- If there are no actionable findings, skip comment subagents and state that clearly.

Do not fix findings unless the user separately asks for implementation.

## 7. Report opinions to the user

Include:

1. Reviewer provider, exact model, exact provider effort identifier, and how any informal effort request was resolved.
2. Fixed comparison point and spec source.
3. Whether resumability was verified, plus any tool requests, approvals, rejections, or reviewer interruptions that affected coverage.
4. For each reviewer comment: the reviewer's final position, the implementing agent's validity classification and opinion, a clear one-sentence explanation, and a clear one-sentence suggested response or resolution.
5. Any unresolved disagreement, missing context, or unverified claim.

Keep Standards and Spec findings separate. Preserve file and line references. Never describe the cross-provider review as a human approval or a substitute for human review.
