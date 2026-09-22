# Agent Skills

Personal Cursor plugin with user-level skills that previously lived only on this machine (`~/.codex/skills`, `~/.cursor/skills`, `~/.claude/skills`).

This repo is a [Cursor team marketplace](https://cursor.com/docs/plugins.md#team-marketplaces) with one plugin, `agent-skills`.

## Skills included

- `address-my-comments`
- `address-pr-comments`
- `babysit-pr`
- `box`
- `cross-provider-code-review`
- `docstrings`
- `explain-problem-and-fix`
- `i-have-adhd`
- `implement-with-graphite-stack`
- `investigate-potential-bug`
- `plain-language`
- `sync-skill-across-tools`
- `transcript`

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
ln -s ~/Repos/agent-skills/plugins/agent-skills ~/.cursor/plugins/local/agent-skills
```

Then **Developer: Reload Window**. This does not sync to cloud VMs.

## Updating skills later

Copy the changed skill folder into `plugins/agent-skills/skills/`, commit, and push. Then refresh the team marketplace (or wait for Auto Refresh if you enable it). No automatic sync from your home-directory skill folders is set up.
