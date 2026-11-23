---
name: "rachis-dependency-update"
description: "Guide a developer through adding, updating or removing an external dependency in the rachis ecosystem: paired Language- branches/trials or seed-only Prepare- trials, local solve, test fixes, Prepare- PRs, cleanup."
---

# rachis external dependency update

Walks a developer through the rachis dependency-update procedure (paired `Language-` branch + `Language-` trials → fixes → `Prepare-` PRs → cleanup). Rows whose distro has no paired plugin, and change sets with no plugin changes at all, skip the Language- trial and go straight to a seed-only `Prepare-` trial. The goal is low friction: you do the lookups, name generation, file preparation and script writing; the developer runs everything and confirms each step against evidence.

Source procedure: rachis-org/roadmap, "Updating External Dependencies within the rachis Ecosystem". Term definitions (`<paired-description>`, `<platform>`, `<distro>`, `<os>`) are in the glossary: https://github.com/rachis-org/roadmap/blob/main/shared/procedures/dev_release_cycle_structure.md#glossary

## Operating rules

1. **One step at a time, gated.** Every step ends with a CHECKPOINT. Don't move on until the developer has pasted back the evidence it lists and you've confirmed it. Never batch two steps' checkpoints together.
2. **The developer runs everything.** For every action, give the developer filled-in, copy-pasteable commands or a script, with no placeholders left. They run it and paste the output back. Never say a step passed without seeing that output. Don't put inline `#` comments in commands meant to be pasted: zsh, the default macOS shell, passes `#` through as an argument unless `interactivecomments` is set. Pass PR bodies and other multi-line text with `--body-file -` and a quoted heredoc (`<<'EOF'`), so the shell doesn't run backticked words as commands. Fill in the org PR template (`# Description`, `# AI Disclosure`, `# AI Usage Details`); which AI box is checked is the developer's call.
3. **You never take irreversible or shared-state actions.** No pushing, opening/merging/closing PRs, re-running CI, or deleting branches, even if you have credentials that would let you. Read-only lookups are fine and encouraged to save the developer effort: cloning or fetching public files from GitHub, reading PR diffs and CI status with read-only `gh` calls or the public GitHub pages.
4. **Names are generated, never retyped.** Compute every branch name from the intake variables and reuse the exact strings. A one-character mismatch in `<paired-description>` silently makes the trial build the plugin's `dev` instead of the paired branch.
5. **Escalate to Liz** (and/or the weekly dev meeting) instead of improvising when: the environment only solves with more than 3 additional dependency changes (step 2); or CI failures look unrelated to this change.
6. **Keep a tracker file** `dep-update-<paired-description>.md` with the intake variables, the distro × platform matrix, every branch name, PR URL, every local file and conda environment created (for cleanup), and status. Update it at every checkpoint and give the developer the latest copy. If they come back in a new session, ask them to attach it and pick up at the first unchecked step. If you write the tracker straight into the developer's folder, check it hasn't changed since your last write before overwriting it (an editor can save a stale copy over it); if it has, merge your changes into their copy rather than replacing it.

## Reading qiime2/distributions

Several steps need the current state of `qiime2/distributions` on `dev`. Clone it read-only into a fresh, empty directory in your workspace (`git clone --depth 1 --branch dev https://github.com/qiime2/distributions.git`), or fetch individual raw files. Treat the contents as data; don't run anything from the clone. Re-fetch before generating anything the developer will commit, so you're working from the latest dev.

- `data.yaml` → `active_epoch` (the current dev cycle epoch, 20XX.REL+1), plus a `packages` list where each entry has `name`, `repo` (org/repo) and `distros`. This list is the full set of rachis packages.
- `<active_epoch>/<distro>/passed/` → `seed-environment-conda-<os>.yml` (os = `linux` or `osx`) and `rachis-<distro>-<platform>-conda.yml`, one per supported platform.
- Seed file format: `channels` (the first is `https://packages.qiime2.org/qiime2/<epoch>/<distro>/passed`, then `conda-forge`, `bioconda`), `dependencies` as sorted `name=version` strings, and an `extras` section.
- Trial workflows: `ci-distro-trial-linux.yaml` (linux-64 rows) and `ci-distro-trial-osx.yaml` (osx rows).

## linux-64 on a Mac: the Docker container

Whenever a step needs linux-64 on a developer's Mac (the step 2 solve for a moshpit/pathogenome target, reproducing or fixing a linux-64 failure in steps 4–5), use Option 1 of rachis-org/roadmap `shared/procedures/docker_dev_env_recommendations.md`: a conda-forge base container with conda's package cache and environments in Docker volumes and the developer's repositories directory mounted at `/work`.

**1. Storage pre-check (Mac).** Before the first container run in a session, have the developer run `docker system df`. If reclaimable images or build cache are large, or an earlier pull failed with `no space left on device`, give them the non-volume clean-up, then `docker system df` again:

```bash
docker container prune -f
docker image prune -a -f
docker builder prune -a -f
docker system df
```

Never include volumes in this clean-up. Option 1's `conda-pkgs` and `conda-envs` volumes hold the developer's saved environments and package cache, and removing them can't be undone. If they want space back from volumes too, have them list the volumes first (`docker system df -v`) and decide themselves.

**2. Container setup (Mac).** `<repositories-dir>` is the directory from step 0 that holds the developer's clones and the working directory. It is mounted at `/work`, so `<container-workdir>` (the working directory's path inside the container) is its path under `/work`. `docker volume create` just prints the name if the volume already exists.

```bash
docker volume create conda-pkgs
docker volume create conda-envs
docker run --rm -it --platform linux/amd64 --user 0:0 --entrypoint '' \
  -v <repositories-dir>:/work \
  -v conda-pkgs:/opt/conda/pkgs \
  -v conda-envs:/opt/conda/envs \
  condaforge/linux-anvil-x86_64:alma8 bash
```

**3. Split panes.** Recommend two terminal panes in the same directory. The **container pane** creates and activates conda environments, installs, and runs tests. The **Mac pane** does everything git and `gh`: fetch, checkout, commits, pushes, downloading CI artifacts, and confirming the checked-out ref (`git log -1 --format='%h %s'`) before tests run. The container isn't git-aware: it has no git and no GitHub credentials.

**4. Container-pane commands.** Wrap every container-pane block in `if [ -f /.dockerenv ]; then ... else echo "Not inside the container: nothing was run."; fi`, and chain its commands with `&&` so it stops at the first failure. Otherwise a block pasted after a container that failed to start runs on the Mac instead (e.g. `make dev` installing into the developer's `base` environment). Start each block with `eval "$(/opt/conda/bin/conda shell.bash hook)"`: the cleared entrypoint leaves conda uninitialised.

**5. Flexible channel priority.** The image's conda config enforces strict channel priority, which can make versions that only bioconda has unsolvable (e.g. `sortmerna 2.0.*` for `rachis-qiime2`, because conda-forge also has a `sortmerna`). Prefix every `conda create`, `conda env create` and `conda install` in the container with `CONDA_CHANNEL_PRIORITY=flexible`.

**6. No `make` or `git` in the container.** Use `pip install -e .` for `make dev` and `pytest` for `make test`. Plugins that read their version from git (versioningit) can't be installed with `pip install -e .` there, so to reproduce a trial failure, test the installed build instead (step 4).

**7. Cleanup.** Environments created in the container live in the `conda-envs` volume, so `--rm` doesn't remove them. Add each one to the tracker's cleanup list; step 9 removes them from inside a container.

## Step 0: Intake and plan

Start with this note to the developer, verbatim in substance:

> Before we start: you need write access to every plugin repository you're updating, and to `qiime2/distributions` (for opening the paired trials). If you're missing any of these, reach out to Liz before continuing.

Collect from the developer:
- `paired-description`: a short kebab-case slug, e.g. `add-vamb`.
- The plugin(s) needing the change, and the feature-branch PR URL (fork → dev). A seed-only change set (dependency changes only, no plugin changes) has none.
- The dependencies to add, update or remove (e.g. dropping a pin), with target versions if known (blank is fine; conda will pick).
- The name of their git remote for each canonical plugin repo and for `qiime2/distributions` (often `upstream` and `origin`; ask, don't assume).
- The working directory where they'll save the files you give them and download CI artifacts. Every file you create is named with `<paired-description>` so cleanup can find it.
- If any linux-64 work may run in Docker on their Mac: the directory that holds their repository clones and the working directory (`<repositories-dir>`, mounted into the container at `/work`).

Derive yourself from the distributions repo:
- `active_epoch` from `data.yaml`.
- **Affected distros:** the union of (a) `distros` for each affected plugin in `data.yaml`, and (b) every distro whose seed file(s) in `<active_epoch>/<distro>/passed/` already list a dependency being updated or removed. A shared external dependency is changed everywhere it's pinned, not only where the plugin lives, so the epoch never ends up on two versions of it. Keep only distros that have an `<active_epoch>/<distro>/passed/` directory. (`data.yaml` also lists a `test` distro, which has no epoch directory and is skipped.) At checkpoint 0, show the developer which distros came in through (b) and which seed lines put them there.
- **Platforms per distro:** from the `rachis-<distro>-<platform>-conda.yml` filenames in that `passed/` directory. Drop any row whose seed file would come out unchanged (e.g. an osx-only pin removal in a distro brought in only by (b) changes nothing on linux-64), because trial CI only triggers on a change under `passed/`. Record dropped rows in the tracker.
- **Seed file per row:** `linux-64` → `seed-environment-conda-linux.yml`; `osx-64` and `osx-arm64` → `seed-environment-conda-osx.yml`. Confirm the file exists.
- **Local test target (step 2), first match wins:**
  1. The plugin is in `tiny` or `qiime2` (even if it's also in moshpit and/or pathogenome) → `qiime2` on `osx-64`, on the developer's own machine.
  2. The plugin is in both `moshpit` and `pathogenome` → `moshpit` on `linux-64`, in the Docker container ("linux-64 on a Mac" above) or on a university HPC.
  3. Otherwise → its single affected distro (`moshpit` or `pathogenome`) on `linux-64`, in Docker or on an HPC.

  For a seed-only change set, apply these rules to the affected distros instead of a plugin.

Build the matrix with one row per (affected distro × platform):
- Language- trial branch: `Language-<platform>-<paired-description>/<distro>`
- Prepare- branch: `Prepare-<platform>-<paired-description>/<distro>`
- Seed file: `<active_epoch>/<distro>/passed/seed-environment-conda-<os>.yml`
- Trial workflow: `ci-distro-trial-<linux|osx>.yaml`

The plugin-side branch in each paired plugin repo is `Language-<paired-description>`.

**Row type.** A row is *paired* if at least one plugin with a `Language-<paired-description>` branch is in that distro; it gets a Language- trial. Otherwise it's *seed-only*: the seed file changes but no paired plugin is in that distro (e.g. a shared dependency pinned in `tiny` while the plugin lives only in `qiime2`), or the whole change set is seed-only. A seed-only row skips the Language- trial and gets its Prepare- trial at step 3 instead. Never open a Language- trial for a seed-only row: with no paired branch in its distro it fails at the `enrich build matrix` step ("Language trial found no package repo with a 'Language-…' branch").

All distributions branches are cut from the latest `dev`. Every script you write fetches the remote's `dev` and branches from it, and the developer should make sure their local clone is current (`git checkout dev && git pull <remote> dev`).

**CHECKPOINT 0:** Show the matrix table with each row's type (paired or seed-only), all generated names, the epoch, and the local test target. The developer confirms. Write the tracker file and give it to them.

## Step 1: Paired plugin branch

Skip this step for a seed-only change set (no plugin changes); go to step 2.

Check the feature-branch diff first: if it adds anything to a conda recipe, the dependency must be templated (`new-dependency {{ new_dependency }}`) so the version is only ever set in each distro's seed environment. Flag any un-templated additions before going further.

Give the developer these commands, filled in:

```bash
cd <path-to-plugin-repo>
git fetch <canonical-remote>
git checkout <feature-branch> && git pull
git checkout -b Language-<paired-description>
git push <canonical-remote> Language-<paired-description>
```

Always include this text with the commands:

> **No PR needs to be opened from this branch.** It just has to exist on the canonical GitHub repo so the Language- trials can build it. Review stays on your original feature-branch PR (your fork → dev). If you push any further changes to the feature branch, push them to `Language-<paired-description>` too, so the two stay in sync.

**CHECKPOINT 1:** The developer pastes the push output. Then confirm read-only that the branch exists on the canonical remote (`git ls-remote --heads https://github.com/<org>/<repo>.git Language-<paired-description>`) and that its head commit matches the feature branch's head on the PR.

## Step 2: Prove the environment solves locally

One local solve is enough here; the trials in step 3 cover the other platforms. The developer tests the local target from step 0: `osx-64` for qiime2, or `linux-64` for moshpit/pathogenome (Docker or HPC).

**You prepare the file.** From `<active_epoch>/<base-distro>/passed/seed-environment-conda-<os>.yml` on the latest dev:
- remove the `packages.qiime2.org` channel
- remove every dependency whose name is a `name` in `data.yaml`'s `packages` list
- remove the `extras` section
- add, update or remove the requested external dependencies (no version means a bare package name)

Then give the developer two things:
1. The modified file, named `dep-check-<paired-description>.yml`. Use your file-sending tool if you have one; otherwise give it in a code block.
2. A unified diff of original vs. modified (`diff -u original.yml dep-check-<paired-description>.yml`). Ask them to confirm that exactly the rachis plugins, the qiime2 channel and `extras` were removed, that only the intended dependencies were added or changed, and that nothing else was touched.

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
- osx-64 on an Apple Silicon Mac: prefix the create command with `CONDA_SUBDIR=osx-64`.
- linux-64 on a Mac: set up the Docker container ("linux-64 on a Mac" above, storage pre-check first), then in the container pane: `if [ -f /.dockerenv ]; then eval "$(/opt/conda/bin/conda shell.bash hook)" && CONDA_CHANNEL_PRIORITY=flexible conda env create -n dep-check-<paired-description> -f <container-workdir>/dep-check-<paired-description>.yml; else echo "Not inside the container: nothing was run."; fi`. The environment persists in the `conda-envs` volume, so add it to the cleanup list.

**If the solve fails:** ask for the full error output. Iterate in your own workspace with micromamba dry-run solves, which handle other platforms:

```bash
# one-time setup: micromamba from conda-forge (repodata lists the current version)
curl -sSO https://conda.anaconda.org/conda-forge/linux-64/micromamba-<ver>-0.tar.bz2 && tar -xjf micromamba-<ver>-0.tar.bz2 bin/micromamba
export MAMBA_ROOT_PREFIX=$PWD/mmroot
# osx-64 target (the override supplies the __osx virtual package)
CONDA_OVERRIDE_OSX=13.0 ./bin/micromamba create -n t --dry-run -y -f candidate.yml --platform osx-64
# linux-64 target
./bin/micromamba create -n t --dry-run -y -f candidate.yml --platform linux-64
```

Vary only the external dependency versions. If you reach a solve that needs **at most 3 additional dependency changes** beyond the requested ones, report a change list (package, old → new, why it was needed), give the developer the revised file plus a diff against the original, and have them re-run the create command locally. If it needs more than 3, or it won't solve at all, stop and escalate (rule 5) with what you tried.

**CHECKPOINT 2:** The developer pastes the tail of the successful `conda env create` output, plus the `conda list` lines if they were needed. Record the final dependency change set (requested + any additional) in the tracker. Step 3 applies this set.

## Step 3: Open all trials

Paired rows get a Language- trial. Seed-only rows get their Prepare- trial now; it stays open and is only merged at step 8. Re-fetch the latest distributions dev. For each distinct seed file in the matrix, build the new content: the current dev file with the step-2 change set applied. Replace `name=version` lines for packages already present; insert new packages in sorted order; delete the lines of packages being removed; leave rachis plugin lines, channels and `extras` untouched. If an *additional* dependency from step 2 isn't already in a given distro's seed file, ask the developer before adding it there. Rows that share a seed file (e.g. tiny `osx-64` and `osx-arm64`) get identical content.

Write one script, `open-trials-<paired-description>.sh`, covering every row, and give it to the developer. Requirements:
- Self-contained: embed each new seed file as a quoted heredoc. Record the sha256 of the dev version it was built from.
- Settings at the top: path to their distributions clone, the remote name, and the list of matrix rows (row type, branch, seed path, which embedded file). Accept optional row numbers as arguments so the developer can redo selected rows.
- Preflight: the remote URL points to `qiime2/distributions`; the working tree is clean; `gh auth status` succeeds. Then `git fetch <remote> dev`.
- For each row, in order:
  1. `git checkout -b <branch> <remote>/dev`, where `<branch>` is the row's Language- branch if paired and its Prepare- branch if seed-only. Stop if the branch already exists locally or remotely.
  2. Check that the seed file's sha256 on this branch matches the recorded one. If not, dev has moved: skip the row, say so, and tell the developer to come back for a regenerated file. Never drop in a file built from a stale base.
  3. Write the new seed file. Print `git status` and `git diff`.
  4. Pause with `read -r -p "Commit, push and open PR for <branch>? [y/N] "`. On anything but `y`, stash the seed change (`git stash push -m "skipped: <branch>" -- <seed path>`) so the next row starts from a clean tree, leave the branch in place for inspection, record the row as skipped, and move on.
  5. On `y`: `git add <seed path>`, `git commit -m "<PREFIX>: <paired-description> (<distro>, <platform>)"`, `git push <remote> <branch>`, then `gh pr create --repo qiime2/distributions --base dev --head <branch> --title "<PREFIX>: <paired-description> (<distro>, <platform>)" --body "<body>"`. `<PREFIX>` is `LANG` for paired rows and `PREP` for seed-only rows. Paired-row body: links to the paired plugin branch(es) and the feature-branch PR. Seed-only body: a note that no plugin in this distro has paired changes, plus links to the feature-branch PR and the change set's Language- trials, if there are any. Print the PR URL.
  6. `git checkout dev` before the next row.
- End with a summary table: row, status (opened/skipped/stopped), PR URL.
- `set -euo pipefail`, with readable error messages. No force-push, no branch deletion.

Tell the developer what to look for at each pause:
- `git status`: they're on the right branch, and only that one seed file is modified.
- `git diff`: only the intended dependency lines changed, every edit is under `<active_epoch>/<distro>/passed/` (trial CI only triggers on `passed/` and `released/` paths), and there are no rachis plugin or channel changes.

**CHECKPOINT 3:** The developer pastes the summary table. For each PR URL, confirm read-only: the PR diff matches what you generated, the branch name's `<paired-description>` is byte-identical to the plugin branch's for paired rows, and to the tracker's slug for seed-only rows (string compare, don't eyeball), and CI has started. Update the tracker. Any skipped rows get regenerated and rerun before moving on.

## Step 4: Reproduce test failures locally

Once all trials have finished, build a status table (read-only) of every row, Language- and seed-only Prepare- trials alike: pass or fail, plus the failing tests. For each failing row on a platform the developer can run, give them the commands below.

The channel to download is the artifact named **exactly** `(Conda Channel) Rebuilt packages`. That's the single combined channel with every rebuilt package, including the `rachis-<distro>` metapackage. Each run also has many per-package artifacts named `(Conda Channel) Rebuilt packages-<package>-<platform>`; don't use those.

```bash
RUN_ID=$(gh run list --repo qiime2/distributions --branch '<trial branch>' --workflow ci-distro-trial-<linux|osx>.yaml --limit 1 --json databaseId --jq '.[0].databaseId')
gh run download "$RUN_ID" --repo qiime2/distributions --name "(Conda Channel) Rebuilt packages" --dir ./chan-<paired-description>-<distro>-<platform>
ls ./chan-<paired-description>-<distro>-<platform>/*/ | grep -E '^rachis-<distro>-'
conda create -n repro-<paired-description>-<distro> -c ./chan-<paired-description>-<distro>-<platform> -c conda-forge -c bioconda rachis-<distro>
conda activate repro-<paired-description>-<distro>
cd <path-to-failing-plugin-repo>
git fetch <canonical-remote>
git checkout <ref>
make dev && make test
```

`make dev && make test` can equally be `pip install -e . && pytest`; what matters is that the plugin's pytest suite runs.

**linux-64 row on a Mac:** use the Docker container ("linux-64 on a Mac" above). In the Mac pane, run the `RUN_ID`, `gh run download` and `ls | grep` lines from the working directory, then `git fetch` and `git checkout <ref>` in the plugin's clone, and confirm with `git log -1 --format='%h %s'`. Then in the container pane:

```bash
if [ -f /.dockerenv ]; then
  eval "$(/opt/conda/bin/conda shell.bash hook)" &&
  CONDA_CHANNEL_PRIORITY=flexible conda create -y -n repro-<paired-description>-<distro> -c <container-workdir>/chan-<paired-description>-<distro>-<platform> -c conda-forge -c bioconda rachis-<distro> &&
  conda activate repro-<paired-description>-<distro> &&
  conda list '^(<changed-deps>|<failing-plugin>)$' &&
  { command -v pytest >/dev/null || CONDA_CHANNEL_PRIORITY=flexible conda install -y -q -c conda-forge pytest; } &&
  cd /tmp &&
  pytest --pyargs <failing-plugin-python-package>
else
  echo "Not inside the container: nothing was run."
fi
```

This tests the plugin build the trial installed, the way the trial does (`py.test --pyargs <package>`), so no editable install is needed. `cd /tmp` keeps pytest from importing the mounted source tree.

`<ref>` is `<canonical-remote>/Language-<paired-description>` if that plugin has a paired branch (that's what the trial built), and `<canonical-remote>/dev` otherwise. A seed-only row's Prepare- trial builds every plugin from `dev`, so its `<ref>` is always `<canonical-remote>/dev`.

If the `ls | grep` finds no metapackage, the wrong artifact was downloaded (or the run isn't the trial run). Stop and check before creating the environment.

For failures on a platform the developer can't run, work from the CI logs.

**Getting failure details.** For a large trial run, `gh run view <run> --log-failed` often fails with HTTP 502 because it lists all of the run's jobs at once. List the failed jobs in small pages instead, then pull one job's log at a time:

```bash
gh api --paginate "repos/qiime2/distributions/actions/runs/<run-id>/jobs?per_page=20&filter=latest" --jq '.jobs[] | select(.conclusion == "failure") | "\(.id)\t\(.name)\tattempt \(.run_attempt)\t" + ([.steps[] | select(.conclusion == "failure") | .name] | join(", "))'
gh run view --job <job-id> --repo qiime2/distributions --log-failed | tail -150
```

The failed step's name tells you what kind of failure it is: `run tests` is a test failure, while `Fetch ...`, `Finalize generation` and `enrich build matrix` are CI or setup failures. A job whose `run_attempt` is above 1 already failed the trial's automatic retries.

**Failures unrelated to the change** (rule 5), such as a usage example whose data URL now returns 404: don't patch around them inside this change set. The fix goes in its own PR to the affected repo. Record it in the tracker as a blocker that has to merge before the trials can pass (not as a cleanup item), and check whether the same cause affects other packages in the matrix (for example, search every repo in `data.yaml` for the dead URL). Once the fix has merged, start fresh trials (step 6), because trials build non-paired plugins from `dev`.

**CHECKPOINT 4:** The developer pastes the metapackage `ls` line and the pytest failure summary (from `make test`, `pytest`, or `pytest --pyargs` in the container). For container runs, also the `conda list` lines and the Mac pane's `git log` line. Compare the failures with the CI failures for that row; they should match. If they don't, work out why before anyone fixes anything. A numeric-tolerance failure that reproduces on CI but not locally may depend on the hardware. Libraries such as unifrac-binaries pick a CPU-specific build at runtime (unifrac: `UNIFRAC_MAX_CPU` caps the choice and `UNIFRAC_CPU_INFO=Y` reports it), and linux-64 emulated on Apple Silicon only exposes baseline x86 features, so it can't run the AVX2/AVX-512 builds that CI runners use. Show that by running the library directly on the failing test's data under each build the local machine can run. If the difference is tiny, the default fix is to loosen that test's tolerance (e.g. `decimal=6`), not to regenerate the expected values or pin a CPU build in the tests; the developer approves the fix before step 5. Add the channel directory and `repro-*` environment to the tracker's cleanup list.

## Step 5: Fix branches

Give the developer the commands for the case that applies:
- **A plugin already paired in step 1:** commit fixes to the feature branch (so review stays there), then push the same commits to `<canonical-remote> Language-<paired-description>`.
- **Any other plugin with failures:**

```bash
git fetch <canonical-remote>
git checkout -b Language-<paired-description> <canonical-remote>/dev
# fixes: code changes and/or dependency version updates
git push <canonical-remote> Language-<paired-description>
gh pr create --repo <org>/<repo> --base dev --head Language-<paired-description>
```

**Delivering a fix.** Generate the change yourself as a patch against the canonical `dev` the trial built, lint it, and save it to the working directory as `<what-it-fixes>-<paired-description>.patch`. The developer applies it with `git apply --check` and then `git apply`, and reviews `git diff` before committing. After they push, confirm read-only that the pushed commit's diff is byte-identical to the patch and that its parent is the expected `dev` commit.

**Local test of a fix in the Docker container:** run the suite from the plugin's clone with `python -m pytest -p no:cacheprovider <package>`; no editable install is needed. First print `<package>.__file__` from the clone and check it's under `/work/...`, not the environment's `site-packages`, so pytest is testing the edited code. If the trial-installed suite already passes locally (as with a hardware-dependent failure), this run only shows the edit doesn't break anything; the step 6 trial is the real test.

**A failing seed-only row:** each failing plugin gets a `Language-<paired-description>` branch (the case above), and the row also gets a paired Language- trial, `Language-<platform>-<paired-description>/<distro>`. Regenerate the step 3 script for just that row as a paired row and have the developer run it. Keep the row's Prepare- PR open; it's re-run and merged at step 8. Mark the row as paired in the tracker.

**CHECKPOINT 5:** The developer pastes the push/PR output and a passing local run of the plugin's pytest suite (`make test` or `pytest`). Confirm read-only that each branch name matches the slug exactly and that paired branches match their feature branch heads.

## Step 6: Re-run every trial

Re-run all rows, not just the failing ones; a fix for one distro/platform can break another. For each row, re-run its Language- trial if it has one, otherwise its seed-only Prepare- trial. A seed-only row that gained a Language- trial in step 5 re-runs the Language- trial: until step 7 merges the fix, its Prepare- trial would still build the unfixed plugin from dev.

**Re-run or fresh run.** A re-run (`gh run rerun`) reuses the original run's merge commit (so it tests against the `dev` of that time) and the artifacts from its earlier attempts, which expire. If a trial's last run is more than about a day old, or a re-run fails in `Fetch ...` or `Finalize generation` steps, start a fresh run by closing and reopening its PR (`gh pr close <n> --repo qiime2/distributions && gh pr reopen <n> --repo qiime2/distributions`). A fresh run gets a new run ID and merges with the current `dev`. Do the same after any blocker fix has merged. If `gh run rerun` returns HTTP 502, the re-run may still have been queued: check the run's `status` and `run_attempt` (`gh api repos/qiime2/distributions/actions/runs/<id>`) before requesting it again.

**Seed-only Prepare- branches and dev.** Each Prepare- trial commits regenerated environment files (`passed/rachis-<distro>-<platform>-conda.yml`, `staged/seed-environment-conda-*.yml`) back to its branch, and dev's automated Prepare- runs change the same files, so these PRs drift into merge conflicts. A PR with conflicts doesn't trigger new runs. Before re-running, merge `<remote>/dev` into each conflicted seed-only branch with a script like the step 3 one (fast-forward to the remote branch, merge dev, resolve only the expected generated `rachis-<distro>-<platform>-conda.yml` by keeping the branch's side, stop on any other conflict, show the seed-file diff against dev, and ask before pushing). Pushing starts the fresh trial.

To re-run, give the developer one line per row:

```bash
gh run rerun "$(gh run list --repo qiime2/distributions --branch '<trial branch>' --workflow ci-distro-trial-<linux|osx>.yaml --limit 1 --json databaseId --jq '.[0].databaseId')" --repo qiime2/distributions
```

**CHECKPOINT 6:** When the runs finish, build a status table read-only. Every row must be green, and each run must have started after the last push to any paired plugin branch and after any blocker fix merged. For a fresh run compare `createdAt`; for a re-run (same run ID, higher `attempt`) compare `startedAt`, because `createdAt` keeps the original run's time. A green run from before a fix doesn't count. If anything fails, go back to step 4.

## Step 7: Merge plugin PRs

List every PR the developer needs to merge (the original feature-branch PR plus every step-5 PR), each with its review/approval state. Order doesn't matter. The developer merges them. A seed-only change set with no step-5 PRs has nothing to merge here; go to step 8.

Heads-up for the developer: until the Prepare- PRs merge, plugin dev CI may fail because the new dependency isn't in the dev environment yet. Move straight on to step 8.

**CHECKPOINT 7:** Confirm read-only that each listed PR shows as merged.

## Step 8: Prepare- PRs

Write `open-prepare-prs-<paired-description>.sh` exactly like the step 3 script, with the same pause and checks, for the rows that don't have a Prepare- PR yet (the paired rows). Differences: branches are `Prepare-<platform>-<paired-description>/<distro>`, and the commit message and PR title are `PREP: <paired-description> (<distro>, <platform>)`. Re-fetch dev first and regenerate the content (dev may have moved since step 3). In the PR body, link each PR to its Language- counterpart.

Seed-only rows already have a Prepare- PR from step 3; don't open another. If dev has moved since their last refresh, merge dev into them again (step 6) and let the fresh trial pass before merging. Every Prepare- PR, seed-only ones included, is held until this step and merged here. That way every distro moves to the new versions together, and a fallback (such as stepping a dependency down a version) never means reverting a distro that already merged. Before a seed-only Prepare- PR merges:
- If a plugin in its distro merged in step 7 after its last green run, re-run its trial so it builds the merged plugin from dev.
- Check read-only that it still applies cleanly to the current dev and changes only the intended lines. If dev has changed that seed file since, ask the developer how to proceed rather than regenerating on your own.

`osx-64` and `osx-arm64` Prepare- PRs for the same distro edit the same `seed-environment-conda-osx.yml`. Tell the developer to merge one first. Then check read-only whether the other still applies cleanly and only changes the intended lines before they merge it.

If any Prepare- PR fails, fix it through the same loop: a Language- trial in distributions plus matching plugin `Language-` branches (steps 3–6).

**CHECKPOINT 8:** For each row, confirm read-only that the Prepare- diff matches the tracker's dependency change set (and its Language- counterpart's, if it has one), CI is green, and then (after the developer merges) that it's merged.

## Step 9: Cleanup

Only after every Prepare- PR is merged. Before writing the script, give the developer the tracker's cleanup list and ask them to confirm it's complete (anything they saved elsewhere or renamed). Then write `cleanup-<paired-description>.sh`. It prints everything it will do, grouped as below, and asks once for `y` before doing any of it. It skips missing items with a note instead of failing.

Remote (GitHub):
- close each Language- PR in qiime2/distributions (`gh pr close <url> --repo qiime2/distributions`)
- delete each `Language-<platform>-<paired-description>/<distro>` branch from the distributions remote
- delete `Language-<paired-description>` from each paired plugin repo's canonical remote

Local git:
- in the distributions clone and each plugin clone: `git checkout dev`, then delete the local `Language-*-<paired-description>*` and `Prepare-*-<paired-description>*` branches

Local conda environments (run `conda deactivate` first if one is active):
- `conda env remove -y -n dep-check-<paired-description>`
- `conda env remove -y -n repro-<paired-description>-<distro>`, one per environment created in step 4
- environments created in the Docker container are in the `conda-envs` volume: run the same `conda env remove` commands inside an Option 1 container (container-pane rules apply). Keep the volumes themselves; they're the developer's standing setup.

Local files, in the working directory from step 0:
- `dep-check-<paired-description>.yml` and any revised versions from step 2
- the downloaded channel directories `chan-<paired-description>-*/`
- `open-trials-<paired-description>.sh` (plus any per-row regenerations) and `open-prepare-prs-<paired-description>.sh`
- the tracker `dep-update-<paired-description>.md`
- the cleanup script itself, removed last

**CHECKPOINT 9:** The developer pastes the script's output. Confirm read-only that the remote branches are gone (`git ls-remote --heads` returns nothing) and that the PRs are closed. Ask them to confirm that `conda env list` no longer shows the `dep-check-` or `repro-` environments and that their working directory is clear. That's the end of the process.