#!/usr/bin/env python

import subprocess
import sys

from alp.common import ActionAdapter

VALID_PREFIXES = [
    # standard development prefixes
    'NEW', 'IMP', 'MAINT', 'DEPR', 'API', 'REF', 'TEST', 'BUG', 'PIN',
    # non-standard
    'CI', 'DOC',
    # to be ignored by the release-changelog collator
    'SKIP', 'REL', 'LANG', 'PREP'
]

def main(gh_token, gh_repo, pr_number):
    title = subprocess.check_output(
        [
            'gh', 'api',
            f'repos/{gh_repo}/pulls/{pr_number}',
            '--jq', '.title',
        ],
        text=True,
    ).strip()

    for prefix in VALID_PREFIXES:
        if title.startswith(f'{prefix}:'):
            print(f'PR title validation passed! (prefix: {prefix})')
            return

    print('PR title validation failed:')
    print(f'Title "{title}" does not begin with a valid prefix.')
    print('Valid prefixes: ' + ', '.join(f'{p}:' for p in VALID_PREFIXES))
    sys.exit(1)


if __name__ == '__main__':
    ActionAdapter(main)
