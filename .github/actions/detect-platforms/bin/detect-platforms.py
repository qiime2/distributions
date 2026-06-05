#!/usr/bin/env python

import os
import json
import sys

from alp.common import ActionAdapter


def add_platform(matrix_entries, detected_platforms, platform_label,
                 runner_label, seed_env_file, conda_subdir,
                 reports, staged_seed_env):

    if not os.path.isfile(staged_seed_env):
        print(f'Found resolved environment support for {platform_label}'
              f' but missing staged seed environment: {staged_seed_env}')
        sys.exit(1)

    matrix_entries.append({
        'platform_label': platform_label,
        'runner_label': runner_label,
        'seed_environment_file': seed_env_file,
        'conda_subdir_env': conda_subdir,
        'upload_reports': reports
    })

    detected_platforms.append(platform_label)


def main(epoch, distro):
    matrix_entries = []
    detected_platforms = []
    passed_dir = os.path.join(epoch, distro, 'passed')
    staged_dir = os.path.join(epoch, distro, 'staged')

    # linux-64
    if os.path.isfile(f'{passed_dir}/rachis-{distro}-linux-64-conda.yml'):
        seed_env_fp = 'seed-environment-conda-linux.yml'
        staged_seed_env = os.path.join(staged_dir, seed_env_fp)
        add_platform(
            matrix_entries, detected_platforms, 'linux-64', 'ubuntu-latest',
            seed_env_fp, '', True, staged_seed_env)

    # osx-64
    if os.path.isfile(f'{passed_dir}/rachis-{distro}-osx-64-conda.yml'):
        seed_env_fp = 'seed-environment-conda-osx.yml'
        staged_seed_env = os.path.join(staged_dir, seed_env_fp)
        add_platform(
            matrix_entries, detected_platforms, 'osx-64', 'macos-15-intel',
            seed_env_fp, '', False, staged_seed_env)

    # osx-arm64
    if os.path.isfile(f'{passed_dir}/rachis-{distro}-osx-arm64-conda.yml'):
        seed_env_fp = 'seed-environment-conda-osx.yml'
        staged_seed_env = os.path.join(staged_dir, seed_env_fp)
        add_platform(
            matrix_entries, detected_platforms, 'osx-arm64', 'macos-15',
            seed_env_fp, 'osx-arm64', False, staged_seed_env)

    # env file not found
    if len(matrix_entries) == 0:
        print('No resolved environment files were found for '
              f'{distro} in {passed_dir}')
        sys.exit(1)

    json_matrix = json.dumps({'include': matrix_entries})

    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
        fh.write(f'active-epoch={epoch}\n')
        fh.write(f'platform-matrix={json_matrix}\n')

    print(f'Detected supported platforms for distro {distro}'
          f' in epoch {epoch}:')
    for platform in detected_platforms:
        print(f'  {platform}')


if __name__ == '__main__':
    ActionAdapter(main)
