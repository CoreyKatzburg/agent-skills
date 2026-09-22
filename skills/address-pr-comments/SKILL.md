---
name: address-pr-comments
description: Pull the open review comments on a PR with the gh CLI, investigate each with a subagent, and report a one-sentence explanation and suggested response per comment.
metadata:
  short-description: Pull and triage open PR review comments
---

# review-pr-comments

Please read the open comments currently on the pr referenced by the user by pulling them using the gh cli tool. For each comment, please have a subagent investigate the related code to fully understand the issue. Use a highly capable model for each subagent (e.g. latest GPT high, opus/fable model). If possible, always run subagents in background mode so the user can send other messages without interrupting the subagents. When done, have the subagents report back to you with their findings on their assigned issue. Then, provide to me a clear, simple, one sentence explanation of each issue, and one sentence on how to address/respond to each comment and/or how to resolve the issue.
