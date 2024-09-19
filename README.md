# Introduction
This repository stores the generated conda environment files for QIIME 2 distributions for a given release cycle (hereafter known as "epoch").


# Github Actions
These are used by maintainers to build and deploy various components of a QIIME 2 distribution.

## Manual Triggers
| **Name** | **Description** | **Preconditions** |
| :--- | :--- | :--- |
| [**cron-prepare\***](https://github.com/qiime2/distributions/actions/workflows/cron-prepare.yaml) | Set up consecutive distribution trials for the [active epoch](https://github.com/qiime2/distributions/blob/dev/data.yaml#L2). | Initial seed environments exist for each distribution in the epoch directory. |
| [**create-prepare-pr**](https://github.com/qiime2/distributions/actions/workflows/create-prepare-pr.yaml) | Set up a single distribution trial for the [active epoch](https://github.com/qiime2/distributions/blob/dev/data.yaml#L2). | Initial seed environments exist for the distribution selected. |
| [**release-docker**](https://github.com/qiime2/distributions/actions/workflows/release-docker.yaml) | Build and publish a docker container to quay.io using the [Dockerfile](https://github.com/qiime2/distributions/blob/dev/Dockerfile)| There exists a repository that `qiime2+q2d2` may push to on quay.io and the release environment exists for the selected distribution and epoch. |

\* Also runs on a cron schedule (over the weekend). This cron often will fail, but can be restarted by re-running the failed PR and then re-running the most recent cron-prepare which will resume waiting on and issuing PRs.

## Automated Triggers
| **Name** | **Description** | **Preconditions** |
| :--- | :--- | :--- |
| [**ci-distro-trial**](https://github.com/qiime2/distributions/actions/workflows/cron-prepare.yaml) | Run a trial for a given distro and epoch. There is specialized behavior for different branch names (see below.) | Any change is made to the seed environment of a *single* distribution (and epoch) within a Pull Request. |

### Specialized branch behavior
For `ci-distro-trial` the behavior will depend on the branch name:

The most general behavior is to identify what has changed in the environment, patch dependent plugins to support any different versions, and run tests. In the event a branch matching the name of the source PRs branch is found in the plugin, that plugin will be rebuilt from that branch before building the distro and testing.

When the branch matches the pattern `Prepare-<epoch>/<distro>[anything else]`,
all packages will be rebuilt and tested from the default branch. Built packages will be uploaded as a conda channel to [packages.qiime2.org](https://packages.qiime2.org/qiime2) under the respective `/qiime2/<epoch>/<distro>/passed/` directory.

When the branch matches the pattern `Language-<anything>/<distro>[anything else]`,
all packages will be rebuilt and tested from the `Language-<anything>` branch if it exists, else the default. It is recommended to set the PR to a draft so that built packages are not uploaded under the `/passed/` directory. Once this PR has passed all checks, it can be converted from draft status and the final action (`upload-builds/commit-changes`) will need to be re-run in order for all of the packages to be uploaded to the relevant channel.

When the branch matches the pattern `Release-<epoch>/<distro>[anything else]`,
all packages will be rebuilt and tested from the `Release-epoch` branch (note that any text after the slash is not a part of the package's branch). Built packages will be uploaded as a conda channel to [packages.qiime2.org](https://packages.qiime2.org/qiime2) under the respective `/qiime2/<epoch>/<distro>/released/` directory.

## Creating a new distribution
When creating a new distribution, the following steps should be taken.

In a PR (branch name doesn't matter):
1. Add the distribution name to the top-level `distros` list within [data.yaml](https://github.com/qiime2/distributions/blob/6b391ec747a9172a460dbbf44650477b19bc277f/data.yaml#L7)
2. For all existing plugins that should be included, make sure the new distro name is added to their `distros` entry within data.yaml (example [here](https://github.com/qiime2/distributions/blob/6b391ec747a9172a460dbbf44650477b19bc277f/data.yaml#L24)).
3. For any new plugins that should be added, create new (alphabetized) entries in data.yaml with the plugin name, the github repo URL, and the distributions it should be included in (example [here](https://github.com/qiime2/distributions/blob/6b391ec747a9172a460dbbf44650477b19bc277f/data.yaml#L10-L12)).

Once these changes are in place, this PR can then be merged into dev (no GHAs will run with changes to data.yaml).

Before a new Prepare PR can be created to test this distribution, the new distro-specific channel will need to be added on our static site server (i.e. packages.qiime2.org). SSH into the server, add the new channel under the current development epoch, and within that channel add directories for `staged`, `passed`, and `released`.

Once this channel has been added, a Prepare PR can be opened (branch name must begin with `Prepare-`) with the following changes:
1. Under the current development epoch directory, create a new subdirectory for the new distribution. Within this new distro subdirectory, create a `passed` directory.
2. Under `<new-distro>/passed`, create a `seed-environment-conda.yml` file. This file will contain all of the plugins and their templated dependencies, along with the channels where they should be installed from (example [here](https://github.com/qiime2/distributions/blob/dev/2024.10/metagenome/passed/seed-environment-conda.yml)).
3. Start filling in this file by including all of the necessary plugins within this distribution (i.e. qiime2, q2-types, etc). For each plugin that's included, check their `ci/recipe/meta.yaml` file for any dependencies with this templated structure. These are the dependencies that must be added into the recipe in addition to the primary plugins contained in the distro. If you're unsure of what version to assign to these dependencies, just look at the current development epoch environment file for another distribution where they're included (this templating structure will only be used for distro inclusive plugins).
4. Once all plugins and their templated dependencies have been added, make sure to include the correct channels at the top of the file. The first channel should be any existing distribution's current development epoch `passed` channel (example [here](https://github.com/qiime2/distributions/blob/6b391ec747a9172a460dbbf44650477b19bc277f/2024.10/metagenome/passed/seed-environment-conda.yml#L2)). The subsequent channels should be `conda-forge` and `bioconda`.

Once all relevant information has been filled in, open these changes as a PR on distributions (note that it must be opened as a branch on the canonical remote vs. from a forked remote). A full Prepare workflow will run, and any issues with package builds and/or test failures can be addressed from here.

Once the Prepare PR is passing, it can be merged and the new distribution can be added to the [`cron-prepare`](https://github.com/qiime2/distributions/blob/dev/.github/workflows/cron-prepare.yaml) workflow for weekly dev builds.

## Building Docker Images locally

Edit `EPOCH` within the top level `Makefile` to the current release epoch:

```bash
EPOCH := foo
```

Please ensure that `EPOCH` is a valid release, with a published environment file under 20XX.REL (within this repository).

Note that `DISTRO` is currently set to `metagenome`, but this may need to be changed in the future as additional distributions are released within the QIIME 2 ecosystem.

### Docker

Navigate to this repository on your local machine and make sure to have Docker desktop running in the background before running the following (note that you'll need quay.io access):

```bash
# Build the docker image locally
$ make docker
# After inspecting the image, login to Docker Hub:
$ docker login quay.io
# Then push both latest and version builds up:
$ docker push quay.io/qiime2/DISTRO:latest
$ docker push quay.io/qiime2/DISTRO:20XX.REL
# LOGOUT
$ docker logout quay.io
```
