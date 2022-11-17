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


def install_requires(reqs):
    print(f'Installing: {" ".join(reqs)}', flush=True)
    subprocess.run(['conda', 'install', '-c', sys.argv[2], '-c', 'conda-forge',
                    '-c', 'bioconda', '-c', 'defaults', '-y', '-q', *reqs],
                    check=True)


def run_imports(imports):
    for imp in imports:
        print(f'Importing: {imp}', flush=True)
        importlib.import_module(imp)


def run_commands(commands):
    for cmd in commands:
        print(f'Running: {cmd}', flush=True)
        subprocess.run(cmd, shell=True, check=True)


def main(conda_pkg):
    tests = find_tests(conda_pkg)
    if 'requires' in tests:
        install_requires(tests['requires'])
    if 'imports' in tests:
        run_imports(tests['imports'])
    if 'commands' in tests:
        run_commands(tests['commands'])


if __name__ == '__main__':
    conda_pkg = sys.argv[1]
    main(conda_pkg)
