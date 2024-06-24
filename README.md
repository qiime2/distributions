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
all packages will be rebuilt and tested from the `Language-<anything>` branch if it exists, else the default. It is recommended to set the PR to a draft so that built packages are not uploaded under the `/passed/` directory.

When the branch matches the pattern `Release-<epoch>/<distro>[anything else]`,
all packages will be rebuilt and tested from the `Release-epoch` branch (note that any text after the slash is not a part of the package's branch). Built packages will be uploaded as a conda channel to [packages.qiime2.org](https://packages.qiime2.org/qiime2) under the respective `/qiime2/<epoch>/<distro>/released/` directory.

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
