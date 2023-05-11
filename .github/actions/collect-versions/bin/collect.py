#!/usr/bin/env python
from alp.common import ActionAdapter


def main(packages, changed, versions_path):
    with open(versions_path, 'w') as fh:
        for change in changed:
            fh.write(f'{change}={packages[change]}\n')


if __name__ == '__main__':
    ActionAdapter(main)
