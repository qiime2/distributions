Created April 2026 by codex

# Workflow Refactor Summary

This note captures the earlier design discussion about reducing duplication in
the split distro workflows while preserving the current Linux / macOS Intel /
macOS arm behavior.

## Goal

Move shared workflow machinery into reusable, platform-parameterized workflows,
while keeping only thin trigger/router wrappers where GitHub Actions requires
platform-specific entry points.

The desired long-term shape is:

- one shared workflow implementation per phase
- platform behavior provided through explicit inputs
- thin wrappers for trigger/routing only
- no duplicated job graphs unless platform behavior truly differs

## Current Platform Vocabulary

Use conda-style platform labels consistently:

- `linux-64`
- `osx-64`
- `osx-arm64`

These labels should be the canonical identifiers used in:

- branch naming
- workflow inputs
- solved environment filenames
- human-facing workflow messaging where practical

## Why Refactor

The current split-by-file layout works, but it creates maintenance costs:

- the same orchestration logic exists in multiple workflow files
- trigger logic is duplicated across Intel/arm/Linux
- fixes need to be copied into multiple places
- workflow naming and routing can drift

The refactor should reduce duplication without forcing Linux and macOS into an
overgeneralized mega-workflow full of conditionals.

## Design Principle

Unify implementation, not behavior.

That means:

- shared workflows should accept a small, explicit input contract
- wrappers should own routing and trigger behavior
- platform-specific differences should remain inputs, not hidden logic
- avoid one giant workflow with many nested `if` branches

## Proposed End State

### Shared Reusable Workflows

Eventually aim for reusable workflows for:

- `create-prepare-pr`
- `cron-prepare`
- top-level trial orchestration
- `prepare`
- `build-generation`
- `build-metapackage`
- `test-metapackage`
- `upload-builds`

### Thin Wrappers / Routers

Keep platform-specific wrappers only where GitHub Actions needs them:

- Linux trigger workflow(s)
- macOS PR router
- Intel/arm cron wrappers
- manual entry points where helpful

## First Refactor Target

The safest first chunk discussed was unifying the `create-prepare-pr-*`
workflows.

Reasoning:

- high duplication
- low platform risk
- mostly string templating and orchestration
- easy to validate
- easy to roll back

This should happen before trying to unify build-generation.

## Proposed Unified `create-prepare-pr` Contract

Required inputs:

- `distro`
- `platform_label`
- `seed_environment_file`
- `trial_workflow_name`

Optional inputs:

- `draft`

Expected `platform_label` values:

- `linux-64`
- `osx-64`
- `osx-arm64`

### Derived Values

From those inputs, the reusable workflow should derive:

- prepare branch name:
  - `Prepare-${platform_label}-${epoch}/${distro}/${date}`
- resolved env filename:
  - `qiime2-${distro}-${platform_label}-conda.yml`
- prepare PR title / commit text
- latest-env PR commit text

### Platform-Specific Wrappers

Linux wrapper:

- `platform_label: linux-64`
- `seed_environment_file: seed-environment-conda-linux.yml`
- `trial_workflow_name: ci-distro-trial-linux`

Intel wrapper:

- `platform_label: osx-64`
- `seed_environment_file: seed-environment-conda-osx.yml`
- `trial_workflow_name: ci-distro-trial-osx`

Arm wrapper:

- `platform_label: osx-arm64`
- `seed_environment_file: seed-environment-conda-osx.yml`
- `trial_workflow_name: ci-distro-trial-osx`

## Trigger / Router Recommendation

The clean macOS split should use a router workflow instead of two separate PR
trigger workflows listening to the same seed environment file.

Reason:

- both Intel and arm PR workflows will start if they share the same
  `pull_request.paths`
- GitHub Actions does not allow clean `head_ref` filtering in the trigger
  itself
- job-level skipping works but is noisy

Preferred approach:

- one PR-triggered macOS router workflow
- reusable Intel and arm trial workflows underneath
- router chooses the correct downstream workflow based on branch naming

This is why consistent platform naming matters.

## Suggested Refactor Order

### Iteration 1

Unify:

- `create-prepare-pr-*`
- `cron-prepare-*`

Success criteria:

- same PR behavior as today
- same branch names and trial launches
- fewer duplicated workflow files

### Iteration 2

Unify top-level orchestration:

- reusable trial-orchestration workflow
- thin Linux/macOS wrappers or routers

Success criteria:

- same job graph
- no behavioral drift

### Iteration 3

Unify `prepare`.

Success criteria:

- identical outputs/artifacts
- no change in generation matrix behavior

### Iteration 4

Unify:

- `build-metapackage`
- `test-metapackage`

Success criteria:

- tiny distro passes for Linux, osx-64, osx-arm64

### Iteration 5

Unify `build-generation`.

This should be last because it is the most platform-sensitive phase.

Success criteria:

- tiny distro passes everywhere
- then broader validation on real distros

## Things To Avoid

- do not force all platforms into one workflow full of conditionals
- do not derive too much implicitly when an explicit input is clearer
- do not unify containerized Linux behavior and non-container macOS behavior in
  a way that hides real differences

## Main Takeaway

The preferred direction is:

- small reusable workflows with explicit platform inputs
- thin wrappers for triggers and routing
- start with orchestration-heavy workflows first
- leave build-generation for last

That gives the best chance of reducing duplication without destabilizing the
current distro trial system.
