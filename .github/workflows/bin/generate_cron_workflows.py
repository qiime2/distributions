#!/usr/bin/env python

import sys
from jinja2 import Environment, FileSystemLoader


if __name__ == '__main__':

    try:
        epoch = sys.argv[1]
    except Exception:
        raise ValueError('Missing required parameter. '
                         'Epoch must be provided.')

    for os, opsys in [('macos', 'osx'), ('ubuntu', 'linux')]:
        filename = 'cron-' + epoch + '-core-' + os + '-latest.yaml'
        env = Environment(loader=FileSystemLoader('templates'),
                          variable_start_string='{{{',
                          variable_end_string='}}}')
        template = env.get_template('cron-workflow-template.j2')
        with open(filename, 'w') as outfile:
            outfile.write(template.render(input_epoch=epoch,
                                          input_os=os, op_sys=opsys))
