#!/usr/bin/env python

import sys
from jinja2 import Environment, FileSystemLoader


if __name__ == '__main__':
    try:
        epoch = sys.argv[1]
    except Exception:
        raise ValueError('Missing required parameter. Epoch must be provided.')

    distro = 'core'

    for platform in ['macos-latest', 'ubuntu-latest']:
        filename = 'cron-%s-%s-%s.yaml' % (epoch, distro, platform)
        env = Environment(loader=FileSystemLoader('templates'),
                          variable_start_string='{{{',
                          variable_end_string='}}}')
        template = env.get_template('cron-workflow-template.j2')
        with open(filename, 'w') as outfile:
            outfile.write(template.render(epoch=epoch,
                                          distro=distro,
                                          platform=platform))
