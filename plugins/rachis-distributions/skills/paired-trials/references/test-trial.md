# Test mode

Testing one or more plugin PRs distro-wide, with no dependency changes. The trials exist only to run the distros' builds and tests against the paired branches; nothing from them merges into `qiime2/distributions`. Read this alongside `SKILL.md`; the section names match its steps.

## Intake (step 0)

Also collect:
- every feature PR to include, with its repo and head branch
- the distros the developer wants trials for

Then:
- **Check each requested distro contains at least one of the plugins being tested** (`data.yaml` `distros`). A Language- trial whose distro has no paired branch fails at the `enrich build matrix` step, so say which requested distros don't qualify and drop them, or ask the developer to add a PR that does.
- **Use every platform of each requested distro** (from its `passed/` filenames), unless the developer narrows it.
- **Group the PRs by repo.** Each repo gets one `Language-<paired-description>` branch; a repo with several PRs gets a combined branch (SKILL.md step 1).

There's no step 2, no row types (every row is a Language- trial) and no Prepare- branches. Record the mode as **test** in the tracker so later steps don't go looking for a change set.

## Step 3: The trigger comment and PR bodies

The trial workflows only start on a seed-file change, so each row's new seed file is the current dev file with one comment line added at the very top, and nothing else changed:

```yaml
# TEST TRIAL (<paired-description>): no dependency changes. Tests: <PR URL>, <PR URL>
```

List every feature PR the trial covers, as full URLs. Keep it one line; YAML ignores it, so the solved environment is the same as dev's. At the pauses, `git diff` should show exactly that one added line.

- Commit message and PR title: `LANG: <paired-description> (<distro>, <platform>)`.
- PR body: say it's a test-only trial with no dependency changes and must not be merged, and list the feature PRs and the paired `Language-<paired-description>` branches.

## Handling failures (steps 4 and 5)

Reproduce and diagnose failures exactly as in SKILL.md step 4 and `ci-failures.md`. Then, for each failure, ask the developer where the fix goes; there's no default, because it depends on the case:
- **In the original feature PR:** the failure is caused by the change being tested. Commit to the feature branch, then bring `Language-<paired-description>` up to date (push the same commits, or merge the updated feature branch into a combined branch).
- **In a PR to the affected plugin:** the failure is in another plugin that has to adapt. That plugin gets its own `Language-<paired-description>` branch and a PR to its `dev` (SKILL.md step 5). Every trial whose distro contains that plugin then builds the new branch, so update the tracker's rows.

A failure unrelated to the change being tested is handled as in `ci-failures.md`, "Unrelated failures": a separate fix, recorded as a blocker.

## Step 7: Where the PRs stand

The feature PRs, and any plugin PRs opened in step 5, merge through their normal review; that isn't part of this procedure. List them with their state, review decision and checks so the developer knows where each one stands.

**Never merge a test trial PR.** Its only change is the trigger comment, which mustn't land on dev. There are no Prepare- PRs in this mode.

## Cleanup (step 9)

Close every test trial PR (with a comment such as "Test trial for `<paired-description>` finished; not for merging") and delete its branch. Delete each `Language-<paired-description>` plugin branch once the developer no longer needs it for more trials. If they plan to push fixes and run the trials again, ask before including those branches.
