---
name: address-my-comments
description: Help a junior developer understand and selectively address review comments on code changes that may have been written by the user, the agent, or another engineer. Use when the user asks clarifying questions about review feedback, pushes back on a code-review comment, asks why a change was made, or wants to discuss whether a fix is appropriate. Do not use as the primary workflow for fetching GitHub PR comments; use gh-address-comments for that.
metadata:
  short-description: Discuss review comments before changing code
---

# Address My Comments

Use this skill when the user is reviewing code changes or asking questions and wants help understanding review comments, explaining why changes were made, deciding whether feedback is valid, or planning fixes.

## Default Behavior

- Treat pasted review comments as discussion topics unless the user explicitly approves code changes.
- Explain clearly for a junior developer. Avoid jargon; define necessary terms briefly when they matter.
- Investigate related code before judging why a change was made or whether a review comment is correct.
- Separate verified facts from inference.
- Do not commit or push unless the user explicitly asks.

## When The User Asks Why Or Pushes Back

1. Read the relevant diff and surrounding code.
2. Explain what the code currently does.
3. Explain the reason for the change, based on evidence from the code.
4. State whether the change still makes sense.
5. If there is a better approach, describe the approach and the tradeoffs in plain language.

## Code Change Gate

- Do not edit files by default.
- If the user asks for code changes, first summarize the exact proposed changes and wait for explicit approval.
- After approval, make only the agreed changes.
- Do not include unrelated cleanup, drive-by refactors, or extra fixes.

## Completion

- When done, summarize what was answered or changed.
- Call out unresolved questions, unverified assumptions, and checks not run.

I am reviewing some code changes that may have been made by me, you, or someone else (and I am reviewing their PR). Please answer any clarifying questions I have about the code or changes. If I push back or ask why certain changes were made, please investigate the related code to determine what the reason is, and if the changes truly make sense or there is a better/different way they could be implemented. I may request some code changes; if so, do not make any changes until after you manually confirm with me, and once I approve, only make the agreed upon changes (i.e. do not make any changes unrelated to our discussion). Let me know once done, and do not commit or push anything unless explicitly told to do so. I am a junior dev and benefit from clear explanations with no jargon or confusing language.