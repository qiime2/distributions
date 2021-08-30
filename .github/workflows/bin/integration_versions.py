import argparse
import datetime
import json
import os
import sys

import yaml


def main(recipe_dir):
    data_fp = os.path.join(recipe_dir, 'data.yaml')
    cbc_fp = os.path.join(recipe_dir, 'conda_build_config.yaml')

    with open(data_fp) as fh:
        data = yaml.load(fh, Loader=yaml.FullLoader)

    with open(cbc_fp) as fh:
        cbc = yaml.load(fh, Loader=yaml.FullLoader)

    payload = dict()
    for pkg in data['run']:
        payload[pkg] = cbc[pkg.replace('-', '_')][0]

    print(json.dumps(payload))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='get metapackage versions')
    parser.add_argument('recipe_dir', type=str, help='path to recipe dir')

    args = parser.parse_args()

    main(args.recipe_dir)
