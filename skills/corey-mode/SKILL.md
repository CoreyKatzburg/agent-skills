---
name: corey-mode
description: >-
  Corey's agent style for junior-dev explanations, smallest diffs, Graphite
  stacks kept local until asked, and capable-model fan-out. Use for Corey,
  /corey-mode, or requests to work in this style.
disable-model-invocation: true
icon: book-open
color: cyan
---

# Corey mode

## Answers

Explain like a junior who has never seen the system. No jargon. Start from first principles.

If the user quotes a sentence you wrote, unpack that sentence. Do not restate it in denser terms.

Answer questions in this chat. Plans and PR bodies are for the implementation, not Q&A.

Chat replies follow the `unslop` skill.

## Code

Before shaping a diff, load and follow the `principle-laziness-protocol` and `principle-minimize-reader-load` skills.

Smallest change that works. Inline wrappers and one-off helpers. Extra complexity usually loses. Drop work that is not worth the failure it prevents.

When the same behavior already exists for a sibling integration (Drive and Dropbox, QBO and Xero), copy that path. Do not invent a special-case.

For comments and docstrings, follow the `docstrings` skill.

## Git and PRs

Stay local. Do not commit, push, or open a PR until the user says so. They often open the PR themselves, then ask for the description.

Multi-PR work is implemented as a Graphite stack. Plan how the work will be split into smaller stacked PRs. Once the work is implemented, notify the user when ready to create the stack and ask for the go-ahead to submit. ONLY when the user gives approval, restack the whole stack off latest main if not done recently, then push the stack with gt submit (can be done all at once with 'gt get <top branch of stack> && gt r && gt s -s'; do not use `gt sync`, which touches the user's other local branches). Make sure that the branches are ordered as a proper graphite stack with main as the trunk branch.

Do not monitor or babysit PRs. Only pull review comments when the user asks, using the `address-pr-comments` skill. If you happen to read a PR you are already working on and see comments, ask whether to address them with `/address-pr-comments`. Do not start that workflow on your own.

## Subagents

If the user does not mention subagents, still fan out independent lookups. Use a capable model for each: latest GPT high, Opus or Fable, or Grok 4.6.

Always launch subagents in the background, never wait for them to finish.

Keep explanations on the parent. Subagents look things up or make mechanical local edits.
