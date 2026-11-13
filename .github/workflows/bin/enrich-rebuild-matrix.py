#!/usr/bin/env python
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request


REMOTE_CHANNEL_BASE = 'https://packages.qiime2.org/qiime2'

# Language trial branches in this repo are named
# `Language-{platform_label}-{name}/{distro}`; the matching branch in a
# package repo may be platform-specific or shared across platforms.
LANGUAGE_PLATFORM_PREFIX = re.compile(
    r'^Language-(?:linux-64|osx-64|osx-arm64)-'
)


def load_matrix(matrix_path):
    with open(matrix_path) as fh:
        return json.load(fh)


def write_matrix(matrix_path, data):
    with open(matrix_path, 'w') as fh:
        json.dump(data, fh)


def branch_exists(repo, branch):
    result = subprocess.run(
        ['git', 'ls-remote', '--heads',
         f'https://github.com/{repo}.git', branch],
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def language_ref_candidates(sibling_ref):
    """Branch names to look for in a package repo, in order of preference:
    the platform-specific name first, then the platform-less
    `Language-{name}` shared by every platform's trial.
    """
    candidates = [sibling_ref]
    shared_ref = LANGUAGE_PLATFORM_PREFIX.sub('Language-', sibling_ref)
    if shared_ref != sibling_ref:
        candidates.append(shared_ref)
    return candidates


def resolve_ref(repo, sibling_ref, is_language):
    if not sibling_ref:
        return ''

    if is_language:
        for candidate in language_ref_candidates(sibling_ref):
            if branch_exists(repo, candidate):
                return candidate
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


def get_next_build_number(epoch, distro, package_name, package_version,
                          target_subdirs):
    max_build_number = -1
    for subdir in target_subdirs:
        repodata_url = (
            f'{REMOTE_CHANNEL_BASE}/{epoch}/{distro}/staged/{subdir}'
            '/repodata.json'
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


def main(matrix_path, epoch, distro, sibling_ref, is_language, target_subdirs):
    matrix = load_matrix(matrix_path)
    resolved = {}
    target_subdirs = json.loads(target_subdirs)

    with tempfile.TemporaryDirectory() as tmpdir:
        for generation in matrix:
            for repo in generation:
                if repo in resolved:
                    continue

                ref = resolve_ref(repo, sibling_ref, is_language)
                print(f"{repo}: building from "
                      f"{repr(ref) if ref else 'the default branch'}",
                      flush=True)
                repo_dir = os.path.join(tmpdir, repo.replace('/', '__'))
                clone_repo(repo, ref, repo_dir)

                package_name, package_version = get_package_name_and_version(
                    repo_dir
                )
                build_number = get_next_build_number(
                    epoch, distro, package_name, package_version,
                    target_subdirs
                )

                resolved[repo] = {
                    'repo': repo,
                    'ref': ref,
                    'package_name': package_name,
                    'package_version': package_version,
                    'build_number': build_number,
                }

                shutil.rmtree(repo_dir)

    if is_language and not any(pkg['ref'] for pkg in resolved.values()):
        candidates = ' or '.join(
            f"'{c}'" for c in language_ref_candidates(sibling_ref)
        )
        print(f"::error::Language trial found no package repo with a "
              f"{candidates} branch, so it would only rebuild default "
              f"branches and test nothing new. Check the branch name in "
              f"the package repo(s) under test.")
        sys.exit(1)

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
    parser.add_argument('--target-subdirs', required=True)
    parser.add_argument('--sibling-ref', default='')
    parser.add_argument('--is-language', action='store_true')

    args = parser.parse_args()
    main(
        matrix_path=args.matrix_path,
        epoch=args.epoch,
        distro=args.distro,
        sibling_ref=args.sibling_ref,
        is_language=args.is_language,
        target_subdirs=args.target_subdirs,
    )
