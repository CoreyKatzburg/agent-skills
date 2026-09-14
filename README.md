# Agent Skills

Personal Cursor plugin with user-level skills that previously lived only on this machine (`~/.codex/skills`, `~/.cursor/skills`, `~/.claude/skills`).

This repo is a [Cursor team marketplace](https://cursor.com/docs/plugins.md#team-marketplaces) with one plugin, `agent-skills`.

## Skills included

- `address-my-comments`
- `address-pr-comments`
- `architect`
- `arena`
- `automate-me`
- `babysit-pr`
- `blast-radius`
- `box`
- `bro`
- `create-verification-skill`
- `cross-provider-code-review`
- `docstrings`
- `explain-problem-and-fix`
- `figure-it-out`
- `how`
- `i-have-adhd`
- `implement-with-graphite-stack`
- `interrogate`
- `investigate-potential-bug`
- `maintain-verification-skill`
- `no-comments`
- `plain-language`
- `ponytail`
- `ponytail-audit`
- `ponytail-debt`
- `ponytail-help`
- `ponytail-review`
- `poteto-mode`
- `principle-boundary-discipline`
- `principle-build-the-lever`
- `principle-encode-lessons-in-structure`
- `principle-exhaust-the-design-space`
- `principle-experience-first`
- `principle-fix-root-causes`
- `principle-foundational-thinking`
- `principle-guard-the-context-window`
- `principle-laziness-protocol`
- `principle-make-operations-idempotent`
- `principle-migrate-callers-then-delete-legacy-apis`
- `principle-minimize-reader-load`
- `principle-model-the-domain`
- `principle-never-block-on-the-human`
- `principle-outcome-oriented-execution`
- `principle-prove-it-works`
- `principle-redesign-from-first-principles`
- `principle-separate-before-serializing-shared-state`
- `principle-sequence-verifiable-units`
- `principle-subtract-before-you-add`
- `principle-type-system-discipline`
- `recall`
- `reflect`
- `setup-pstack`
- `show-me-your-work`
- `swarm`
- `sync-skill-across-tools`
- `tdd`
- `teach`
- `technical-writing`
- `transcript`
- `typescript-best-practices`
- `unslop`
- `why`

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
