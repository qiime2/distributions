#!/usr/bin/env python
import argparse
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request


REMOTE_CHANNEL_BASE = 'https://packages.qiime2.org/qiime2'
TARGET_SUBDIRS = ('linux-64', 'noarch')


def load_matrix(matrix_path):
    with open(matrix_path) as fh:
        return json.load(fh)


def write_matrix(matrix_path, data):
    with open(matrix_path, 'w') as fh:
        json.dump(data, fh)


def branch_exists(repo, branch):
    result = subprocess.run(
        ['git', 'ls-remote', '--heads', f'https://github.com/{repo}.git', branch],
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def resolve_ref(repo, sibling_ref, is_language):
    if not sibling_ref:
        return ''

    if is_language:
        if branch_exists(repo, sibling_ref):
            return sibling_ref
        return ''

    return sibling_ref


def clone_repo(repo, ref, dest):
    cmd = ['git', 'clone', '--quiet']
    if ref:
        cmd.extend(['--branch', ref, '--single-branch'])
    cmd.extend([f'https://github.com/{repo}.git', dest])
    subprocess.run(cmd, check=True)


def get_package_name_and_version(repo_dir):
    report_path = os.path.join(repo_dir, 'report.json')
    cmd = [
        'pip', 'install', '--dry-run',
        '--report', report_path,
        repo_dir,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    with open(report_path) as fh:
        result_json = json.load(fh)

    pkg_name = result_json['install'][0]['metadata']['name']
    pkg_version = result_json['install'][0]['metadata']['version']
    return pkg_name, pkg_version


def fetch_repodata(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise


def get_next_build_number(epoch, distro, package_name, package_version):
    max_build_number = -1
    for subdir in TARGET_SUBDIRS:
        repodata_url = (
            f'{REMOTE_CHANNEL_BASE}/{epoch}/{distro}/staged/{subdir}/repodata.json'
        )
        repodata = fetch_repodata(repodata_url)

        for section in ('packages', 'packages.conda'):
            for pkg in repodata.get(section, {}).values():
                if (
                    pkg.get('name') == package_name
                    and pkg.get('version') == package_version
                ):
                    max_build_number = max(max_build_number,
                                           pkg.get('build_number', 0))

    return max_build_number + 1


def main(matrix_path, epoch, distro, sibling_ref, is_language):
    matrix = load_matrix(matrix_path)
    resolved = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        for generation in matrix:
            for repo in generation:
                if repo in resolved:
                    continue

                ref = resolve_ref(repo, sibling_ref, is_language)
                repo_dir = os.path.join(tmpdir, repo.replace('/', '__'))
                clone_repo(repo, ref, repo_dir)

                package_name, package_version = get_package_name_and_version(
                    repo_dir
                )
                build_number = get_next_build_number(
                    epoch, distro, package_name, package_version
                )

                resolved[repo] = {
                    'repo': repo,
                    'package_name': package_name,
                    'package_version': package_version,
                    'build_number': build_number,
                }

                shutil.rmtree(repo_dir)

    enriched = [
        [resolved[repo] for repo in generation]
        for generation in matrix
    ]
    write_matrix(matrix_path, enriched)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Enrich rebuild_matrix.json with package metadata.'
    )
    parser.add_argument('--matrix-path', required=True)
    parser.add_argument('--epoch', required=True)
    parser.add_argument('--distro', required=True)
    parser.add_argument('--sibling-ref', default='')
    parser.add_argument('--is-language', action='store_true')

    args = parser.parse_args()
    main(
        matrix_path=args.matrix_path,
        epoch=args.epoch,
        distro=args.distro,
        sibling_ref=args.sibling_ref,
        is_language=args.is_language,
    )
