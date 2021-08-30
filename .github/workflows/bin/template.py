import argparse
import datetime
import os
import sys

from jinja2 import Template
import yaml


def main(recipe_dir, include_tests):
    data_fp = os.path.join(recipe_dir, 'data.yaml')
    tmpl_fp = os.path.join(recipe_dir, 'meta.yaml.jinja')
    recipe_fp = os.path.join(recipe_dir, 'meta.yaml')

    with open(data_fp) as fh:
        data = yaml.load(fh, Loader=yaml.FullLoader)

    with open(tmpl_fp) as fh:
        tmpl = Template(fh.read())

    rendered = tmpl.render(
        data=data,
        include_tests=include_tests,

        # additional context should be added here
        datetime=datetime,
        env=os.environ,
    )

    with open(recipe_fp, 'w') as fh:
        fh.write(rendered)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='render metapackage recipe')
    parser.add_argument('recipe_dir', type=str, help='path to recipe dir')
    parser.add_argument('--tests', default=False, action='store_true',
                        help='include individual package tests?')

    args = parser.parse_args()

    main(args.recipe_dir, args.tests)
