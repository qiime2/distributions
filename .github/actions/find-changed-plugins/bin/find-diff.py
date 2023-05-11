#!/usr/bin/env python
import itertools

import yaml

from alp.common import ActionAdapter


def get_minimal_env(seed_env_path):
    if not seed_env_path:
        return {}

    with open(seed_env_path) as fh:
        env = yaml.safe_load(fh)

    return dict(entry.split('=') for entry in env['dependencies'])

def find_diff(old, new):
    old = get_minimal_env(old)
    new = get_minimal_env(new)

    old_keys = set(old)
    new_keys = set(new)

    removed_pkgs = list(old_keys - new_keys)
    added_pkgs = list(new_keys - old_keys)
    changed_pkgs = list()

    maybe_changed = old_keys & new_keys
    for key in maybe_changed:
        if old[key] != new[key]:
            changed_pkgs.append(key)

    return {
        'changed_pkgs': changed_pkgs,
        'added_pkgs': added_pkgs,
        'removed_pkgs': removed_pkgs,
    }


def main(old_seed_env, new_seed_env):
    diff = find_diff(old_seed_env, new_seed_env)

    return {
        'all_changes': list(
            itertools.chain.from_iterable(diff.values())
        )
    }


if __name__ == '__main__':
    ActionAdapter(main)
