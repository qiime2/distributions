# Trial failures, blockers and re-runs

Read the section a step points you to.

## Getting failure details

For a large trial run, `gh run view <run> --log-failed` often fails with HTTP 502 because it lists all of the run's jobs at once. List the failed jobs in small pages instead, then pull one job's log at a time:

```bash
gh api --paginate "repos/qiime2/distributions/actions/runs/<run-id>/jobs?per_page=20&filter=latest" --jq '.jobs[] | select(.conclusion == "failure") | "\(.id)\t\(.name)\tattempt \(.run_attempt)\t" + ([.steps[] | select(.conclusion == "failure") | .name] | join(", "))'
gh run view --job <job-id> --repo qiime2/distributions --log-failed | grep -E "FAILED|Error:|error:|AssertionError" | head -60
gh run view --job <job-id> --repo qiime2/distributions --log-failed | tail -150
```

The failed step's name tells you what kind of failure it is:
- **`run tests`** (in a `test-metapackage / <plugin> (<platform>)` job) is a test failure.
- **`Fetch ...`, `Finalize generation` or `Check builds in this generation`** are CI or setup failures. On a re-run, these usually mean the original run's artifacts have expired (see "Re-run or fresh run").
- **`enrich build matrix`** on a Language- trial means no package repo in that distro has a matching paired branch.

A job whose `run_attempt` is above 1 already failed the trial's automatic retries. Timeouts on a different build in each generation point to slow runners, not to the change; a full re-run from the top usually clears them.

## Unrelated failures

These are failures that have nothing to do with the change, such as a usage example whose data URL now returns 404. Don't patch around them inside this change set:
1. **The fix goes in its own PR** to the affected repo.
2. **Record it in the tracker as a blocker**, something that has to merge before the trials can pass (not as a cleanup item).
3. **Check whether the same cause affects other packages in the matrix**, for example by searching every repo in `data.yaml` for the dead URL.
4. **Once the fix has merged, start fresh trials** (below), because trials build non-paired plugins from `dev`.

Rule 5 applies: tell the developer (or Liz) what you found and agree the fix before preparing it. If the fix depends on infrastructure that can't be changed soon (e.g. a redirect service that can't deploy), offer a direct but less stable alternative. Spell out the trade-off, and record switching back as a follow-up in the tracker.

## Failures that don't reproduce locally

If CI and the local run disagree, work out why before anyone fixes anything. A numeric-tolerance failure that reproduces on CI but not locally may depend on the hardware:
- **CPU-specific builds:** libraries such as unifrac-binaries pick a CPU-specific build at runtime. For unifrac, `UNIFRAC_MAX_CPU` caps the choice (it can't force a build the CPU doesn't support) and `UNIFRAC_CPU_INFO=Y` reports which one it used.
- **Emulation:** linux-64 emulated on Apple Silicon only exposes baseline x86 features, so it can't run the AVX2/AVX-512 builds that CI runners use.
- **How to show it:** run the library directly on the failing test's data under each build the local machine can run, and compare the values with CI's.

If the difference is tiny, the default fix is to loosen that test's tolerance (e.g. `decimal=6`), not to regenerate the expected values or pin a CPU build in the tests. The developer approves the fix before step 5.

## Re-run or fresh run

A re-run (`gh run rerun`) reuses the original run's merge commit, so it tests against the `dev` of that time. It also reuses the artifacts from earlier attempts, which expire.

**Start a fresh run instead** by closing and reopening the PR (`gh pr close <n> --repo qiime2/distributions && gh pr reopen <n> --repo qiime2/distributions`) when:
- the trial's last run is more than about a day old
- a re-run fails in `Fetch ...` or `Finalize generation` steps
- a blocker fix has merged

A fresh run gets a new run ID and merges with the current `dev`.

**After a 502 from `gh run rerun`:** the re-run may still have been queued. Check the run's `status` and `run_attempt` (`gh api repos/qiime2/distributions/actions/runs/<id> --jq '"\(.status) attempt \(.run_attempt)"'`) before requesting it again.

**A PR with merge conflicts doesn't trigger runs.** Bring the branch up to date with dev first (dependency mode: `dependency-update.md`, "Seed-only Prepare- branches and dev").

For checkpoint 6, compare a fresh run's `createdAt`, or a re-run's `startedAt`, with the time of the last relevant push or merge.
