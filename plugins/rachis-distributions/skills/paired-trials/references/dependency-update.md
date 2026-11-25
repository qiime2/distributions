# Dependency mode

Adding, updating or removing an external dependency across the rachis distros. Read this alongside `SKILL.md`; the section names match its steps.

## Intake (step 0)

Also collect: the dependencies to add, update or remove (e.g. dropping a pin), with target versions if known (blank is fine; conda will pick).

**Affected distros:** the union of
- (a) `distros` for each affected plugin in `data.yaml`, and
- (b) every distro whose seed file(s) in `<active_epoch>/<distro>/passed/` already list a dependency being updated or removed.

A shared external dependency is changed everywhere it's pinned, not only where the plugin lives, so the epoch never ends up on two versions of it. At checkpoint 0, show which distros came in through (b) and which seed lines put them there.

**Drop rows with nothing to change:** drop any row whose seed file would come out unchanged (e.g. an osx-only pin removal in a distro brought in only by (b) changes nothing on linux-64), because trial CI only triggers on a seed-file change. Record dropped rows in the tracker.

**Row type.** A row is *paired* if at least one plugin with a `Language-<paired-description>` branch is in that distro; it gets a Language- trial. Otherwise it's *seed-only*: the seed file changes but no paired plugin is in that distro (e.g. a shared dependency pinned in `tiny` while the plugin lives only in `qiime2`), or the whole change set is seed-only. A seed-only row skips the Language- trial and gets its Prepare- trial at step 3 instead. Never open a Language- trial for a seed-only row: it fails at the `enrich build matrix` step ("Language trial found no package repo with a 'Language-…' branch").

**Local test target (step 2), first match wins:**
1. The plugin is in `tiny` or `qiime2` (even if it's also in moshpit and/or pathogenome) → `qiime2` on `osx-64`, on the developer's own machine.
2. The plugin is in both `moshpit` and `pathogenome` → `moshpit` on `linux-64`, in the Docker container (`linux-64-docker.md`) or on a university HPC.
3. Otherwise → its single affected distro (`moshpit` or `pathogenome`) on `linux-64`, in Docker or on an HPC.

For a seed-only change set, apply these rules to the affected distros instead of a plugin.

Before checkpoint 0, look up the target versions in the conda channels' repodata (e.g. `https://conda.anaconda.org/bioconda/<platform>/repodata.json.zst`) for every platform in the matrix: confirm each version exists, list its new dependencies, and check none of them conflicts with an existing seed pin. Point out if a newer version than the one requested exists.

## Step 2: Prove the environment solves locally

One local solve is enough here; the trials cover the other platforms. The developer tests the local target from step 0.

**You prepare the file.** From `<active_epoch>/<base-distro>/passed/seed-environment-conda-<os>.yml` on the latest dev:
- remove the `packages.qiime2.org` channel
- remove every dependency whose name is a `name` in `data.yaml`'s `packages` list
- remove the `extras` section
- add, update or remove the requested external dependencies (no version means a bare package name)

Then give the developer two things:
1. The modified file, named `dep-check-<paired-description>.yml`.
2. A unified diff of original vs. modified (`diff -u original.yml dep-check-<paired-description>.yml`). Ask them to confirm that exactly the rachis plugins, the qiime2 channel and `extras` were removed, that only the intended dependencies were added or changed, and that nothing else was touched.

Before handing it over, run a micromamba dry-run solve of the file yourself for the target platform (below), so the developer doesn't spend time on a solve that fails.

Commands for the developer:

```bash
conda env create -n dep-check-<paired-description> -f dep-check-<paired-description>.yml
```

Only if some requested dependency had no version specified, add:

```bash
conda activate dep-check-<paired-description>
conda list '^(<dep1>|<dep2>)$'
```

If they had versions, the solve itself is the proof; skip these.

Environment notes, to include only when relevant:
- osx-64 on an Apple Silicon Mac: prefix the create command with `CONDA_SUBDIR=osx-64`, unless the developer already sets that in their conda config.
- linux-64 on a Mac: use the Docker container (`linux-64-docker.md`, storage pre-check first). In the container pane: `if [ -f /.dockerenv ]; then eval "$(/opt/conda/bin/conda shell.bash hook)" && CONDA_CHANNEL_PRIORITY=flexible conda env create -n dep-check-<paired-description> -f <container-workdir>/dep-check-<paired-description>.yml; else echo "Not inside the container: nothing was run."; fi`. The environment persists in the `conda-envs` volume, so add it to the cleanup list.

**If the solve fails:** ask for the full error output. Iterate in your own workspace with micromamba dry-run solves, which handle other platforms. One-time setup: download micromamba from conda-forge (its repodata lists the current version), then:

```bash
curl -sSO https://conda.anaconda.org/conda-forge/linux-64/micromamba-<ver>-0.tar.bz2 && tar -xjf micromamba-<ver>-0.tar.bz2 bin/micromamba
export MAMBA_ROOT_PREFIX=$PWD/mmroot
CONDA_OVERRIDE_OSX=13.0 ./bin/micromamba create -n t --dry-run -y -f candidate.yml --platform osx-64
CONDA_OVERRIDE_GLIBC=2.28 ./bin/micromamba create -n t --dry-run -y -f candidate.yml --platform linux-64
```

(The overrides supply the `__osx` and `__glibc` virtual packages.) Vary only the external dependency versions. If you reach a solve that needs **at most 3 additional dependency changes** beyond the requested ones, report a change list (package, old → new, why it was needed), give the developer the revised file plus a diff against the original, and have them re-run the create command locally. If it needs more than 3, or it won't solve at all, stop and escalate (rule 5) with what you tried.

**CHECKPOINT 2:** The developer pastes the tail of the successful `conda env create` output, plus the `conda list` lines if they were needed. Record the final dependency change set (requested + any additional) in the tracker. Step 3 applies this set.

## Step 3: Seed-file content and PR bodies

For each distinct seed file in the matrix, the new content is the current dev file with the step 2 change set applied:
- replace `name=version` lines for packages already present
- insert new packages in sorted order
- delete the lines of packages being removed
- leave rachis plugin lines, channels and `extras` untouched

If an *additional* dependency from step 2 isn't already in a given distro's seed file, ask the developer before adding it there.

Paired rows open Language- trials (`LANG:`); seed-only rows open their Prepare- trials now (`PREP:`). That PR stays open and is only merged at step 8.
- Paired-row body: the change, plus links to the paired plugin branch(es) and the feature-branch PR(s).
- Seed-only body: the change, a note that no plugin in this distro has paired changes, and links to the feature-branch PR(s) and the change set's Language- trials, if there are any.

At the pauses, `git diff` should show only the dependency lines from the change set.

## Seed-only rows that fail (step 5)

Each failing plugin gets a `Language-<paired-description>` branch (SKILL.md step 5), and the row also gets a paired Language- trial, `Language-<platform>-<paired-description>/<distro>`. Regenerate the step 3 script for just that row as a paired row and have the developer run it. Keep the row's Prepare- PR open; it's re-run and merged at step 8. Mark the row as paired in the tracker. A seed-only row that gained a Language- trial re-runs the Language- trial in step 6: until step 7 merges the fix, its Prepare- trial would still build the unfixed plugin from dev.

## Seed-only Prepare- branches and dev (steps 6 and 8)

Each Prepare- trial commits regenerated environment files back to its branch: `passed/rachis-<distro>-<platform>-conda.yml`, `staged/seed-environment-conda-*.yml`, and newer plugin pins in the seed file. Dev's automated Prepare- runs change the same files, so these PRs drift into merge conflicts, and a PR with conflicts doesn't trigger new runs.

Before re-running, merge `<remote>/dev` into each conflicted seed-only branch with a script like the step 3 one:
- fast-forward the local branch to the remote one (it carries the bot's commits), or create it from the remote if it's missing
- merge `<remote>/dev`
- resolve only the expected generated `rachis-<distro>-<platform>-conda.yml` by keeping the branch's side (the next trial regenerates it); abort and stop on any other conflict
- check for leftover conflict markers, show the seed-file diff against dev and the full file list, and ask before pushing

Pushing starts the fresh trial. Test the script against a copy of the real branches first.

## Step 8: Prepare- PRs

Write `open-prepare-prs-<paired-description>.sh` exactly like the step 3 script, with the same pause and checks, for the rows that don't have a Prepare- PR yet (the paired rows). Differences:
- branches are `Prepare-<platform>-<paired-description>/<distro>`
- the commit message and PR title are `PREP: <paired-description> (<distro>, <platform>)`
- re-fetch dev first and regenerate the content (dev may have moved since step 3)
- in the PR body, link each PR to its Language- counterpart and list the plugin PRs merged in step 7

**Seed-only rows** already have a Prepare- PR from step 3; don't open another. If dev has moved since their last refresh, merge dev into them again (above) and let the fresh trial pass before merging. Before a seed-only Prepare- PR merges:
- If a plugin in its distro merged in step 7 after its last green run, re-run its trial so it builds the merged plugin from dev.
- Check read-only that it still applies cleanly to the current dev and changes only the intended lines. If dev has changed that seed file since, ask the developer how to proceed rather than regenerating on your own.

**Expect the bot's commit.** When a Prepare- trial passes, the bot commits updated plugin pins to its seed file (the builds the trial just produced, e.g. the plugin fixes merged in step 7). Those pins land on dev with the change set; they're also evidence that the trial built the merged fixes.

**Merge all Prepare- PRs together** once every row is green, so every distro moves to the new versions at once. That way a fallback (such as stepping a dependency down a version) never means reverting a distro that already merged. `osx-64` and `osx-arm64` Prepare- PRs for the same distro edit the same `seed-environment-conda-osx.yml`: have the developer merge one first, then check read-only that the other still merges cleanly and only changes the intended lines before they merge it. A plain two-dot diff against dev will also list files that dev changed since the branch was cut; judge the PR by its own changes (`git diff dev...branch`) and a test merge.

If any Prepare- PR fails, fix it through the same loop: a Language- trial in distributions plus matching plugin `Language-` branches (steps 3–6).

**CHECKPOINT 8:** For each row, confirm read-only that the Prepare- diff matches the tracker's dependency change set (and its Language- counterpart's, if it has one) and that CI is green. After the developer merges, confirm on dev that every affected seed file has the new versions and no removed pins, and that the expected plugin pins are in.

## Cleanup extras (step 9)

Add `dep-check-<paired-description>.yml` (and any revisions), its diff, and `open-prepare-prs-<paired-description>.sh` to the files list, and the `dep-check-<paired-description>` environment to the conda list. Merged Prepare- branches are usually already gone from GitHub; the local ones still need deleting.
