#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# fmt: off
# type: ignore



checkname = 'splunk_jobs'


info = [['2019-05-16T11:17:00.000+02:00', 'splunk-system-user', 'DONE', 'False'],
        ['2019-05-16T10:17:01.000+02:00', 'splunk-system-user', 'DONE', 'False']]


discovery = {'': [(None, {})]}


checks = {'': [(None,
                {},
                [(0, 'Job Count: 0', [('job_total', 0, None, None, None, None)]),
                 (0, 'Failed jobs: 0', [('failed_jobs', 0, None, None, None, None)]),
                 (0, 'Zombie jobs: 0', [('zombie_jobs', 0, None, None, None, None)])])]}
