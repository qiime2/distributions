#!/usr/bin/env python
import sys
import yaml
import tarfile
import importlib
import subprocess


def find_tests(conda_pkg):
    with tarfile.open(conda_pkg, mode='r:bz2') as fh:
        recipe_fh = fh.extractfile('info/recipe/meta.yaml')
        tests = yaml.safe_load(recipe_fh).get('test')
    return tests


def run_imports(imports):
    for imp in imports:
        print(f'Importing: {imp}')
        importlib.import_module(imp)


def run_commands(commands):
    for cmd in commands:
        print(f'Running: {cmd}')
        subprocess.run(cmd, shell=True, check=True)


def main(conda_pkg):
    tests = find_tests(conda_pkg)
    run_imports(tests['imports'])
    run_commands(tests['commands'])


if __name__ == '__main__':
    conda_pkg = sys.argv[1]
    main(conda_pkg)
