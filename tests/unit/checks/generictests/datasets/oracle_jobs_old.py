#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# fmt: off
# type: ignore

checkname = 'oracle_jobs'

info = [
    [
        'DB1', 'SYS', 'BSLN_MAINTAIN_STATS_JOB', 'SCHEDULED', '1', '421',
        'TRUE', '09.12.19 00:00:00,000000 +02:00', 'BSLN_MAINTAIN_STATS_SCHED',
        'SUCCEEDED'
    ]
]

discovery = {'': [('DB1.SYS.BSLN_MAINTAIN_STATS_JOB', {})]}

checks = {
    '': [
        (
            'DB1.SYS.BSLN_MAINTAIN_STATS_JOB', {
                'consider_job_status': "ignore",
                'status_missing_jobs': 2,
                'missinglog': 1
            }, [
                (
                    0,
                    'Job-State: SCHEDULED, Enabled: Yes, Last Duration: 1 second, Next Run: 09.12.19 00:00:00,000000 +02:00, Last Run Status: SUCCEEDED (ignored disabled Job)',
                    [('duration', 1, None, None, None, None)]
                )
            ]
        )
    ]
}
