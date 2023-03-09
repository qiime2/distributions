# Overview

Legend:
 * rounded = *start/end*
 * diamond = *descision*
 * flag = *note or manual action*
 * double-bar = *github action (subworkflow)*
 * rectangle = *a step*

## Regular Development
This figure shows the high-level interaction between different components.

```mermaid
flowchart TB
 start([Something Changes!])
 d_1{Is it a dependency \nor code change?}
 n_code>The change affects the package first.]
 n_distro>The change effects the distro first.]
 done([Done])

 start --> d_1
 d_1 -->|code| n_code
 n_code --> github_pr

 d_1 -->|dependency| n_distro
 n_distro -->|push commit to main| integration_trial_pre
 integration_trial_fail --> individual_trial_pr
 individual_trial_merge -->|re-run| integration_trial_gha

 integration_trial_upload --> reindex_complex
 reindex_complex --> final_merge
 final_gha --> done

 github_upload --> reindex_simple
 reindex_simple -->|push commit to main| integration_trial_pre

 subgraph github_repo1[Individual Github Repository]
  github_pr["Open Pull Request (main ← {anything})"]
  github_pr_gha[[GHA: ci_pr.yml]]
  github_pr_check{Success?}
  github_pr_fail>Write better code.]
  github_pr_merge[Merge PR]
  github_main_gha[[GHA: ci_main.yml]]
  github_upload[["ci_main.yml: upload build(s)"]]

  github_pr -->|"trigger (doesn't start with ci)"| github_pr_gha
  github_pr_gha --> github_pr_check
  github_pr_check -->|yes| github_pr_merge
  github_pr_check -->|no| github_pr_fail
  github_pr_fail -->|push commit| github_pr_gha
  github_pr_merge --> github_main_gha
  github_main_gha -->|if succeeded| github_upload
 end

 subgraph github_repo2[Individual Github Repository]
  individual_trial_pr["Open Pull Request (ci-{change}-{ver} ← {anything})"]
  individual_trial_gha[[GHA: ci_trial.yml]]
  individual_trial_fail>Write better code.]
  individual_trial_merge[Merge PR]
  individual_trial_check{Sucess?}

  individual_trial_pr -->|"trigger (starts with ci)"| individual_trial_gha
  individual_trial_gha --> individual_trial_check
  individual_trial_check --->|yes| individual_trial_merge
  individual_trial_check -->|no| individual_trial_fail
  individual_trial_fail -->|push commit| individual_trial_gha
 end

 subgraph github_repo3["Individual Github Repositor(ies)"]
  final_merge["Merge branch (main ← ci-{change}-{ver})"]
  final_conflict{"Success?"}
  todo>"Handle manually\n(new version + build from main)"]
  final_gha[["GHA: ci_main.yml (not triggered)"]]

  final_merge --> final_conflict
  final_conflict -->|yes| final_gha
  final_conflict -->|no| todo
 end

 subgraph integration_repo[qiime2/package-integration]
  integration_trial_pre["Update /staged/ for distro"]
  integration_trial_queue[["GHA: distro_queue.yml"]]
  integration_trial_pr["Open Pull Request (main ← ci-{change}-{ver})"]
  integration_trial_gha[[GHA: ci_distro_trial.yml]]
  integration_trial_check{Success?}
  integration_trial_fail>Bask in failure.]
  integration_trial_upload[[ci_distro_trial.yml: upload builds]]

  integration_trial_pre -->|triggers| integration_trial_queue
  integration_trial_queue -->|once concurrency group is free| integration_trial_pr
  integration_trial_pr --> integration_trial_gha
  integration_trial_gha --> integration_trial_check
  integration_trial_check -->|yes| integration_trial_upload
  integration_trial_check -->|no| integration_trial_fail
 end

 subgraph library1[library.qiime2.org]
  reindex_simple["reindex (no patch updates)"]
 end

 subgraph library2[library.qiime2.org]
  reindex_complex["reindex (with packagedata patches)"]
 end
```

## Distro Release

```mermaid
flowchart TB
  TODO
```

# Github Actions
Sub-workflows for each github action.

## Individual Repository
Github actions for individual plugins or repositories.

### `ci_pr.yml`
Test a pull request (in the usual way)
```mermaid
flowchart TB
  TODO
```


### `ci_main.yml`
Test (and build) a commit pushed to main
```mermaid
flowchart TB
  TODO
```


### `ci_trial.yml`
Test a PR in the context of an existing trial from package-integration
```mermaid
flowchart TB
  start(["A PR exists from (ci-{change}-{ver} ← {anything})"])
  collect["Download partial environment from \n package-integration (ci-{change}-{ver}) \n (Includes patched repodata from trial)"]
  setup["Setup local channels and environment"]
  build["Build package"]
  test["Test built package"]

  start --> collect
  collect --> setup
  setup --> build
  build --> test
```

## Package Integration
Github workflows for creating distributions

### `distro_queue.yml`
Prevents too many GHA runners from being used by arbitrarily many distros
```mermaid
flowchart TB
  start([A distro's /staged/ changes])
  alt_start([A timer has elapsed])
  busy{"Is there a running job\nin QUEUE\nconcurrency group?"}
  replace>"GHA queues this action\n(replacing/canceling any pending job)"]
  workflow_start["Generate diff of each distro"]
  integration_trial_pr["Open Pull Request (main ← ci-{change}-{ver})"]
  random["Pick a random diff"]
  done([Done])

  start & alt_start --> busy
  busy -->|yes| replace
  busy -->|no| workflow_start
  replace -->|once free| workflow_start
  workflow_start --> random
  random --> integration_trial_pr
  integration_trial_pr --> done
```

### `ci_distro_trial.yml`
Produce a new configuration for a distribution
```mermaid
flowchart TB
  start(["A commit exists in a ci-{change}-{ver} branch"])
  busy{"Is there a running job\nin QUEUE\nconcurrency group?"}
  replace>"GHA queues this action\n(replacing/canceling any pending job)"]
  workflow_start["Create DAG of changes"]
  workflow_report["Create report of Trial plan"]
  workflow_matrix["Create matrix generations"]
  done([Done])

  start  --> busy
  busy -->|yes| replace
  busy -->|no| workflow_start
  replace -->|once free| workflow_start
  workflow_start --> workflow_report
```

##### Process and necessary steps/scripts for ci_distro_trial.yml workflow
```mermaid
flowchart TB
  start(["conda_build_config.yml"])
  alt_start(["$REF(ish)"])
  find_diff{"1. find_diff.py"}
  pkg_diffs>"[PKG1, PKG2, etc...]"]
  make_dag{"2. make_dag.py"}
  job_sum(["GHA Job Summary"])
  pkg_diff_vers>"{ 'PKG1 version': [...], 'PKG2 version': [...] }"]
  make_channel{"3. make_channel.py"}
  channel_dir1(["local/conda/channel"])
  patch_channel{"4. patch_channel.py"}
  os_paths>"{ osx: path/to/patch, linux: path/to/patch }"]
  channel_dir2(["local/conda/channel"])
  render_meta["5. render_metapackage"]
  install["6. install"]
  test["7. test"]
  publish["8. publish"]

  start --> find_diff
  alt_start --> find_diff
  find_diff --> pkg_diffs
  pkg_diffs --> make_dag
  start --> make_dag
  make_dag --> job_sum
  make_dag --> pkg_diff_vers
  start --> make_channel
  make_channel --> channel_dir1
  pkg_diff_vers --> patch_channel
  channel_dir1 --> patch_channel
  patch_channel --> os_paths
  patch_channel --> channel_dir2
  channel_dir2 --> render_meta
  render_meta --> install
  install --> test
  test --> publish
  os_paths --> publish
```
