#!/usr/bin/env python

import yaml

from alp.common import ActionAdapter


def main(file):
    with open(file) as fh:
        return dict(data=yaml.safe_load(fh))


if __name__ == '__main__':
    ActionAdapter(main)
