# Agent Skills

Personal Cursor plugin with user-level skills that previously lived only on this machine (`~/.codex/skills`, `~/.cursor/skills`, `~/.claude/skills`).

This repo is one plugin that shares the same `skills/` folder across tools: `plugin.json` and `.agents/plugins/marketplace.json` for Codex, `.cursor-plugin/plugin.json` for Cursor, `.devin-plugin/plugin.json` for Devin, and `.claude-plugin/marketplace.json` for Claude Code (it works as both the marketplace and the plugin definition, so no separate Claude `plugin.json`). Keep the plugin `name`, `version`, and `description` in all four plugin definitions in sync.

## Skills included

- `address-my-comments`
- `address-pr-comments`
- `be-ambitious` — deepen a task without expanding its scope.
- `box`
- `corey-mode`
- `cross-provider-code-review`
- `docstrings`
- `eli5` — a visual HTML explanation for a complete beginner
- `explain-problem-and-fix`
- `goal` — instruction-only goal pursuit with rigorous progress, blocker, and completion checks.
- `html-plan` — an interactive HTML plan with decisions and feedback
- `i-have-adhd`
- `implement-with-graphite-stack`
- `investigate-potential-bug`
- `plain-language`
- `sync-skill-across-tools`
- `transcript`
- `windows-desktop-ssh` — SSH to Corey’s Windows desktop from a managed cloud agent.

`be-ambitious` uses plain Markdown instructions and has no host-specific tool dependencies. The plugin manifests load the shared `skills/` folder in Claude Code, Codex, Devin, and Cursor. Its input rules accept namespaced plugin commands, `/be-ambitious`, skill-picker invocation, or natural-language requests; other agents that load `SKILL.md` can use the same file.


`eli5` and `html-plan` use the same skill files in Claude Code, Codex, Devin, Cursor, and other agents that load `SKILL.md`. They use the task or topic from the user's message and return HTML that opens in a browser; a host-specific artifact viewer is optional. `html-plan` needs Node.js to pack its page, with no package dependencies.

Both are adapted from [Anthropic's community plugins](https://github.com/anthropics/claude-plugins-community/tree/06ec7b6a0a82bdc4bec44bd82d4368c42f20d7c1).

## Add this as a Cursor plugin

### Option A: Team marketplace (needed for Cloud Agents)

1. Open [Cursor Dashboard → Plugins](https://cursor.com/dashboard?tab=plugins).
2. Under **Team Marketplaces**, click **Add Marketplace** → **Import from Repo**.
3. Paste `https://github.com/CoreyKatzburg/agent-skills`.
4. Confirm Cursor finds the `agent-skills` plugin, then save.
5. For a private repo, install the [Cursor GitHub App](https://cursor.com/docs/integrations/github.md) on this repository so Cursor can clone it.
6. In the Cursor app, open **Customize**, find **Agent Skills**, and **Install** at **user** scope (not project).
7. Start a **new** cloud agent. Existing runs will not pick this up.

If install creates an empty cache folder, delete `~/.cursor/plugins/cache/` entries for this marketplace and reinstall. Private-repo clones sometimes need git credentials on the machine (`gh auth setup-git` is enough if `gh` already works).

### Option B: Local plugin (this machine only, not Cloud Agents)

```bash
mkdir -p ~/.cursor/plugins/local
ln -s ~/Repos/agent-skills ~/.cursor/plugins/local/agent-skills
```

Then **Developer: Reload Window**. This does not sync to cloud VMs.

## Add this as a Devin plugin

Devin reads [`.devin-plugin/plugin.json`](https://docs.devin.ai/cli/extensibility/plugins/overview). Skills show up as `/agent-skills:<skill>`.

```bash
# Synced to your Devin account, so cloud sessions get it too
devin plugins install CoreyKatzburg/agent-skills

# This machine only, linked to the checkout so edits are live
devin plugins install --local ~/Repos/agent-skills
```

Run `devin plugins info agent-skills` to confirm the skills loaded, and `devin plugins update agent-skills` after pushing changes. For a private repo, Devin needs GitHub access to it.

## Add this as a Claude Code marketplace

Claude Code looks for `.claude-plugin/marketplace.json` at the repo root.

```bash
/plugin marketplace add CoreyKatzburg/agent-skills
/plugin install agent-skills@corey-agent-skills
```

Skills show up as `/agent-skills:<skill>`. After pushing changes, run `/plugin marketplace update corey-agent-skills`. For a private repo, Claude Code needs GitHub access to it.

## Updating skills later

Copy the changed skill folder into `skills/`, commit, and push. Then refresh the team marketplace (or wait for Auto Refresh if you enable it). No automatic sync from your home-directory skill folders is set up.

## Goal skill

Invoke `$goal <objective>` in Codex, or the equivalent skill invocation exposed by another host (such as `/agent-skills:goal`). The skill includes the full behavioral instructions adapted from Codex's published `/goal` continuation prompt: preserve the original scope, work from current evidence, detect no-progress and verified waits, prioritize fidelity, audit every acceptance criterion, and require three consecutive observable same-blocker turns before declaring blocked. Pause only on an explicit user request.

**Instruction-only:** no Python dependencies, background jobs, MCP tools, hooks, persisted goal files, or token counters. The skill does not start new turns or provide native lifecycle tracking; use Codex's built-in `/goal` if you need those runtime features.
