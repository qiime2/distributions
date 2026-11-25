# linux-64 on a Mac: the Docker container

Whenever a step needs linux-64 on a developer's Mac, use Option 1 of rachis-org/roadmap `shared/procedures/docker_dev_env_recommendations.md`. Examples: the step 2 solve for a moshpit/pathogenome target, or reproducing, diagnosing or fixing a linux-64 failure in steps 4–5. Option 1 is a conda-forge base container with conda's package cache and environments in Docker volumes and the developer's repositories directory mounted at `/work`.

## 1. Storage pre-check (Mac)

Before the first container run in a session, have the developer run `docker system df`. If reclaimable images or build cache are large, or an earlier pull failed with `no space left on device`, give them the non-volume clean-up, then `docker system df` again:

```bash
docker container prune -f
docker image prune -a -f
docker builder prune -a -f
docker system df
```

Never include volumes in this clean-up. Option 1's `conda-pkgs` and `conda-envs` volumes hold the developer's saved environments and package cache, and removing them can't be undone. If they want space back from volumes too, have them list the volumes first (`docker system df -v`) and decide themselves.

## 2. Container setup (Mac)

`<repositories-dir>` is the directory from step 0 that holds the developer's clones and the working directory. It is mounted at `/work`, so `<container-workdir>` (the working directory's path inside the container) is its path under `/work`. `docker volume create` just prints the name if the volume already exists.

```bash
docker volume create conda-pkgs
docker volume create conda-envs
docker run --rm -it --platform linux/amd64 --user 0:0 --entrypoint '' \
  -v <repositories-dir>:/work \
  -v conda-pkgs:/opt/conda/pkgs \
  -v conda-envs:/opt/conda/envs \
  condaforge/linux-anvil-x86_64:alma8 bash
```

## 3. Split panes

Recommend two terminal panes in the same directory:
- **Container pane:** creates and activates conda environments, installs, and runs tests.
- **Mac pane:** everything git and `gh`. That means fetch, checkout, commits and pushes, downloading CI artifacts, and confirming the checked-out ref (`git log -1 --format='%h %s'`) before tests run.

The container isn't git-aware: it has no git and no GitHub credentials.

## 4. Container-pane rules

- **Guard every block.** Wrap every container-pane block in `if [ -f /.dockerenv ]; then ... else echo "Not inside the container: nothing was run."; fi`, and chain its commands with `&&` so it stops at the first failure. Otherwise a block pasted after a container that failed to start runs on the Mac instead (e.g. `make dev` installing into the developer's `base` environment).
- **Initialise conda.** Start each block with `eval "$(/opt/conda/bin/conda shell.bash hook)"`: the cleared entrypoint leaves conda uninitialised.
- **Use flexible channel priority.** The image's conda config enforces strict channel priority, which can make versions that only bioconda has unsolvable (e.g. `sortmerna 2.0.*` for `rachis-qiime2`, because conda-forge also has a `sortmerna`). Prefix every `conda create`, `conda env create` and `conda install` with `CONDA_CHANNEL_PRIORITY=flexible`.
- **No `make` or `git`.** Use `pip install -e .` for `make dev` and `pytest` for `make test`. Plugins that read their version from git (versioningit) can't be installed with `pip install -e .` here. So test the installed build (section 5) or the clone directly (section 6) instead.

## 5. Reproducing a trial failure (step 4)

In the Mac pane, run the `RUN_ID`, `gh run download` and `ls | grep` lines from SKILL.md step 4 in the working directory. Then `git fetch` and `git checkout <ref>` in the plugin's clone, and confirm with `git log -1 --format='%h %s'`. Then in the container pane:

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

This tests the plugin build the trial installed, the way the trial does (`py.test --pyargs <package>`), so no editable install is needed. `cd /tmp` keeps pytest from importing the mounted source tree. To rebuild an existing repro environment from scratch, add `{ conda env remove -y -n repro-<paired-description>-<distro> || true; } &&` before the create. Emulated linux-64 on Apple Silicon can't run AVX2/AVX-512 code paths; see `ci-failures.md`, "Failures that don't reproduce locally".

## 6. Testing a fix (step 5)

Run the suite from the plugin's clone; no editable install is needed. First print the package's `__file__` from the clone and check it's under `/work/...`, not the environment's `site-packages`, so pytest is testing the edited code:

```bash
if [ -f /.dockerenv ]; then
  eval "$(/opt/conda/bin/conda shell.bash hook)" &&
  conda activate repro-<paired-description>-<distro> &&
  cd /work/<path-to-plugin-clone> &&
  python -c "import <package>; print(<package>.__file__)" &&
  python -m pytest -p no:cacheprovider <package>
else
  echo "Not inside the container: nothing was run."
fi
```

If the trial-installed suite already passed locally (as with a hardware-dependent failure), this run only shows the edit doesn't break anything; the step 6 trial is the real test. To run a single failing test file, pass its path instead of `<package>`.

## 7. Cleanup

Environments created in the container live in the `conda-envs` volume, so `--rm` doesn't remove them. Add each one to the tracker's cleanup list. The step 9 script removes them with a one-off container (skip with a note if Docker isn't running or the image isn't downloaded):

```bash
docker run --rm --platform linux/amd64 --user 0:0 --entrypoint '' -v conda-envs:/opt/conda/envs -v conda-pkgs:/opt/conda/pkgs condaforge/linux-anvil-x86_64:alma8 /opt/conda/bin/conda env remove -y -n <env>
```

Keep the volumes and the image; they're the developer's standing setup.
