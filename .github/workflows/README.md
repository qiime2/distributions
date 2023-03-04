# QIIME 2 Package Integration: Github Workflows

This directory contains all of the scripts used for generating the GitHub
workflow files for each epoch.

# Generate cron workflows

This script will generate cron workflow files for the provided epoch and distro for both
macOS and linux. It should be run from `.github/workflows/bin` with the
following invocation:

```bash
python generate_cron_workflows.py 20XX.XX EPOCH
```

When these cron workflow files are generated, they should be manually moved to
`.github/workflows` with the rest of the cron workflow files for previous
epochs.
