#!/usr/bin/env python
import yaml
import json
import os
import sys
import subprocess
import copy
from collections import defaultdict

SUBDIRS = ['linux-64', 'noarch', 'osx-64']


def write_config(pkgs_in_distro, dest):
    config_yaml = {'blacklist': [{'name': '*'}]}
    whitelist = []

    for pkg, version in pkgs_in_distro.items():
        whitelist.append({'name': pkg, 'version': version})

    config_yaml['whitelist'] = whitelist
    with open(dest, 'w') as fh:
        yaml.safe_dump(config_yaml, fh)


def create_channel(epoch, distro, channel_dir, config):
    REMOTE_CHANNEL = \
        f'https://packages.qiime2.org/qiime2/{epoch}/staged/{distro}'
    CMD_TEMPLATE = ('conda-mirror --upstream-channel %s --target-directory %s '
                    '--platform %s --config %s')
    for subdir in SUBDIRS:
        cmd = CMD_TEMPLATE % (REMOTE_CHANNEL, channel_dir, subdir, config)
        subprocess.run(cmd.split(), check=True)


def _patch_repodata(repodata, changes):
    packages = repodata['packages']
    instructions = {
        'patch_instructions_version': 1,
        'packages': defaultdict(dict),
        'revoke': [],
        'remove': [],
    }
    # If we only want to patch the newest version of the downstream package
    # that's in repodata I can probably use timestamps
    for updated, downstream in changes.items():
        updated_pkg, new_version = updated
        for pkg, info in packages.items():
            if info['name'] in downstream:
                deps = info['depends']
                for idx, dep in enumerate(deps):
                    if updated_pkg == dep.split()[0]:
                        if instructions['packages'].get(pkg, None) is None:
                            instructions['packages'][pkg] = {}
                            instructions['packages'][pkg]['depends'] = \
                                copy.deepcopy(packages[pkg]['depends'])
                        instructions['packages'][pkg]['depends'][idx] = \
                            f'{updated_pkg} {new_version}'
                        break

    return instructions


def patch_channels(channel_dir, source_revdeps, pkgs_in_distro):
    patch_instructions = {}

    versioned_revdeps = {(pkg, pkgs_in_distro[pkg]): revs
                         for pkg, revs in source_revdeps.items()}

    for subdir in SUBDIRS:
        # The channel name might not end up just being a filepath but we will
        # see, depends on what happens with the github workers and whatever
        with open(os.path.join(channel_dir,
                               subdir, 'repodata.json'), 'r') as fh:
            repodata = json.load(fh)
        patch_instructions = _patch_repodata(repodata,
                                             versioned_revdeps)
        # Similar to the above this filepath
        # probably won't look quite like this in the end
        with open(os.path.join(channel_dir,
                               subdir, 'patch_instructions.json'), 'w') as fh:
            json.dump(patch_instructions, fh, indent=2,
                      sort_keys=True, separators=(",", ": "))

    subprocess.run(['conda', 'index', channel_dir], check=True)


if __name__ == '__main__':
    (epoch,
     distro,
     packages_in_distro_path,
     full_distro_path,
     revdeps_of_sources_path,
     local_channel) = sys.argv[1:]

    with open(packages_in_distro_path, 'r') as fh:
        pkgs_in_distro = json.load(fh)

    with open(full_distro_path, 'r') as fh:
        full_distro = json.load(fh)

    with open(revdeps_of_sources_path, 'r') as fh:
        source_revdeps = json.load(fh)

    os.mkdir(local_channel)

    config = os.path.join(local_channel, 'config.yaml')
    write_config(pkgs_in_distro, config)
    create_channel(epoch, distro, local_channel, config)
    patch_channels(local_channel, source_revdeps, full_distro)
