---
name: eli5
description: Explain a topic to a complete beginner through an HTML page with big pictures and few words. Use when the user invokes eli5 or asks for a simple visual explanation of how something works.
license: Apache-2.0
---

# eli5

Explain like I'm someone who knows nothing about this topic, using an HTML page with big pictures and few words.

Use the topic supplied with the skill invocation or in the user's message. If it is missing and cannot be inferred from the conversation, ask what to explain.

Create one self-contained HTML file with the current agent's file tools. Use inline CSS and SVG or HTML for the pictures so the page works offline without extra packages. Keep the explanation accurate and introduce unfamiliar terms in plain language.

If the current host can display HTML, show it there. Otherwise, give the user a link or attachment to the file and tell them to open it in a browser. No specific artifact tool is required.

## Source

Adapted from [Anthropic's eli5 skill](https://github.com/anthropics/claude-plugins-community/tree/06ec7b6a0a82bdc4bec44bd82d4368c42f20d7c1/eli5), under [Apache-2.0](LICENSE).
Modified for this repository: portable topic input and self-contained HTML output with a browser fallback.
