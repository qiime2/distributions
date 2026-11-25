# rachis-distributions

Claude skills for maintaining rachis distributions in `qiime2/distributions`.

| Skill | Run as | Use it to |
|-------|--------|-----------|
| `paired-trials` | `/rachis-distributions:paired-trials` | Add, update or remove an external dependency across distros (paired `Language-` trials → fixes → `Prepare-` PRs → cleanup), or test one or more plugin PRs distro-wide with test-only `Language-` trials |

You can also just describe the task (for example, "update unifrac-binaries to 1.7 across the distros"), and Claude loads the skill on its own.

## Install (Claude Code)

You need a local clone of `qiime2/distributions`; the skill's procedures make changes there anyway. Point the marketplace at that clone:

```bash
claude plugin marketplace add /path/to/your/distributions
claude plugin install rachis-distributions@rachis
```

Claude Code reads the plugin straight from your clone, so there is no separate download and no update step.

**Getting updates:** pull `dev` in your clone, then start a new session or run `/reload-plugins`. The skill you get is whatever branch your clone has checked out, so if you're on an old feature or `Language-` branch you'll have an older copy of the skill.

**Without a clone:** `claude plugin marketplace add qiime2/distributions`, then the same install command. This downloads its own copy of the whole repository (~55 MB). Update with `claude plugin update rachis-distributions@rachis`.

## Install (claude.ai / Claude desktop)

Paid plans: **Customize → Plugins → Add → Add marketplace**, enter `qiime2/distributions`, then add `rachis-distributions`.

## Editing the skills

Skills live in `skills/<name>/SKILL.md`, with longer material under `skills/<name>/references/`. If you installed from your local clone, your edits load at the next session start or after `/reload-plugins`.

Before opening a PR:

1. Bump `version` in `.claude-plugin/plugin.json`. Users who installed from GitHub only receive changes when this string changes.
2. Validate from the repository root:

   ```bash
   claude plugin validate --strict plugins/rachis-distributions
   claude plugin validate .
   ```

Never change the plugin's `name` (`rachis-distributions`); existing installs are recorded under it. To change the label shown in `/plugin`, edit `displayName`.
