#!/usr/bin/env python

import datetime

from alp.common import ActionAdapter

# cutoff date for which PR template validation should be enforced
# creation & publication of this template was made live at EOD 6 June 2026
# so the date onwards this should be enforced is the following workday
# in Zurich timezone (UTC +2)
PR_TEMPLATE_CUTOFF_ISO = '2026-06-03T07:00:00.000Z'

def _determine_pr_iso(created_at):
    pass


def main():
    pass


if __name__ == '__main__':
    ActionAdapter(main)
