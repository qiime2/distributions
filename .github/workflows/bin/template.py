import datetime
import os
import sys

from jinja2 import Template
import yaml


def main(recipe_dir):
    data_fp = os.path.join(recipe_dir, 'data.yaml')
    tmpl_fp = os.path.join(recipe_dir, 'meta.yaml.jinja')
    recipe_fp = os.path.join(recipe_dir, 'meta.yaml')

    with open(data_fp) as fh:
        data = yaml.load(fh, Loader=yaml.FullLoader)

    with open(tmpl_fp) as fh:
        tmpl = Template(fh.read())

    rendered = tmpl.render(
        data=data,

        # additional context should be added here
        datetime=datetime,
        env=os.environ,
    )

    with open(recipe_fp, 'w') as fh:
        fh.write(rendered)


if __name__ == '__main__':
    recipe_dir = sys.argv[1]

    main(recipe_dir)
