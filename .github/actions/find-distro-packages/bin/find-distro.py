#!/usr/bin/env python
import urllib.request
import yaml

from alp.common import ActionAdapter


def get_library_packages():
    response = urllib.request.urlopen(
        'https://raw.githubusercontent.com/qiime2/distributions/dev/data.yaml')
    return {x['name']: x['repo'] for x in yaml.safe_load(response)['packages']}


def get_minimal_env(seed_env_path):
    with open(seed_env_path) as fh:
        env = yaml.safe_load(fh)

    return dict(entry.split('=') for entry in env['dependencies'])


def main(seed_env):
    library_pkgs = get_library_packages()
    relevant_pkgs = get_minimal_env(seed_env)
    repos = {k: library_pkgs[k] for k in relevant_pkgs if k in library_pkgs}
    versions = {k: relevant_pkgs[k] for k in repos}

    return dict(repos=repos, versions=versions, all=relevant_pkgs)


if __name__ == '__main__':
    ActionAdapter(main)
