import os
import sys
import json
import datetime
from urllib.request import urlopen
import pkg_resources

import yaml

def main(epoch, distro):
    path = os.path.join(epoch, 'staged', distro)
    conda_build_config_path = os.path.join(path, 'conda_build_config.yaml')
    data_path = os.path.join(path, 'data.yaml')

    # we are going to assume that linux and osx are synced.
    conda_channel_repodata = (f'https://packages.qiime2.org/'
                              f'qiime2/{epoch}/tested/linux-64/repodata.json')

    with open(data_path) as fh:
        package_data = yaml.safe_load(fh)
        packages = [x.replace('-', '_') for x in package_data['run']]

    with urlopen(conda_channel_repodata) as fh:
        repodata = json.loads(fh.read())

    latest_versions = {}
    for value in repodata['packages'].values():
        name = value['name'].replace('-', '_')
        version = pkg_resources.parse_version(value['version'])

        if name not in latest_versions:
            latest_versions[name] = version
        else:
            existing_version = latest_versions[name]
            if existing_version <= version:
                latest_versions[name] = version

    # update metapackage version
    with open(data_path, 'w') as fh:
        package_data['version'] = \
            datetime.datetime.utcnow().strftime(r'%Y.%m.%d.%H.%M.%S')
        yaml.dump(package_data, fh)

    # update included package versions to latest
    with open(conda_build_config_path, 'r') as fh:
        conda_build_config = yaml.safe_load(fh)
        for package in packages:
            conda_build_config[package] = [str(latest_versions[package])]

    with open(conda_build_config_path, 'w') as fh:
        yaml.dump(conda_build_config, fh)


if __name__ == '__main__':
    epoch, distro = sys.argv[1:]

    main(epoch, distro)
