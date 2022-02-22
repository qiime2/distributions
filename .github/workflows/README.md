# QIIME 2 Package Integration: Github Workflows

This directory contains all of the scripts used for generating the Github workflow files for each epoch.

# Generate cron workflows

This script will generate cron workflow files for the provided epoch for both Mac OS and Linux.
It should be run within .github/workflows/bin in the following format:

python generate_cron_workflows.py 20XX.XX

With 20XX.XX representing the next release epoch.

When these cron workflow files are generated, they should be manually moved to .github/workflows with the rest of the cron workflow files for previous epochs.
