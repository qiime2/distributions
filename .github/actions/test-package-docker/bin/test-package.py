#!/usr/bin/env python

import importlib
import itertools
import subprocess
import tarfile
import yaml

from alp.common import ActionAdapter


def find_tests(package_path):
    with tarfile.open(package_path, mode='r:bz2') as fh:
        recipe_fh = fh.extractfile('info/recipe/meta.yaml')
        tests = yaml.safe_load(recipe_fh).get('test')
    return tests


def install_requires(reqs, channels):
    print(f'Installing: {" ".join(reqs)}', flush=True)
    channels = itertools.chain.from_iterable(
        [('-c', channel) for channel in channels])
    subprocess.run(['conda', 'install',
                    *channels,
                    '-y', '-q',
                    *reqs],
                   check=True)


def run_imports(imports):
    for imp in imports:
        print(f'Importing: {imp}', flush=True)
        importlib.import_module(imp)


def main(package_path, channels, conda_activate):
    tests = find_tests(package_path)
    print(tests, flush=True)
    if 'requires' in tests:
        install_requires(tests['requires'], channels)
    if 'imports' in tests:
        run_imports(tests['imports'])


if __name__ == '__main__':
    ActionAdapter(main)
