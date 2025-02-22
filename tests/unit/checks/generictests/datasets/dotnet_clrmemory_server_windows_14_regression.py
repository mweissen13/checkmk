#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# fmt: off
# type: ignore

checkname = 'dotnet_clrmemory'

info = [
    [
        'AllocatedBytesPersec', 'Caption', 'Description', 'FinalizationSurvivors',
        'Frequency_Object', 'Frequency_PerfTime', 'Frequency_Sys100NS', 'Gen0heapsize',
        'Gen0PromotedBytesPerSec', 'Gen1heapsize', 'Gen1PromotedBytesPerSec', 'Gen2heapsize',
        'LargeObjectHeapsize', 'Name', 'NumberBytesinallHeaps', 'NumberGCHandles',
        'NumberGen0Collections', 'NumberGen1Collections', 'NumberGen2Collections',
        'NumberInducedGC', 'NumberofPinnedObjects', 'NumberofSinkBlocksinuse',
        'NumberTotalcommittedBytes', 'NumberTotalreservedBytes', 'PercentTimeinGC',
        'PercentTimeinGC_Base', 'ProcessID', 'PromotedFinalizationMemoryfromGen0',
        'PromotedMemoryfromGen0', 'PromotedMemoryfromGen1', 'Timestamp_Object',
        'Timestamp_PerfTime', 'Timestamp_Sys100NS'
    ],
    [
        '766573506832', '', '', '761', '0', '2240904', '10000000', '12582912', '2708256',
        '3461688', '124320', '60014800', '3584288', '_Global_', '67060776', '20831',
        '60934', '7064', '1038', '388', '0', '392', '79908864', '805289984', '377048032',
        '-1', '0', '406627', '2708256', '124320', '0', '4227247572262', '131350801098190000'
    ],
    [
        '0', '', '', '0', '0', '2240904', '10000000', '0', '0', '0', '0', '0', '0',
        'w3wp', '0', '4197', '0', '0', '0', '0', '0', '250', '0', '0', '0', '0', '0',
        '0', '0', '0', '0', '4227247572262', '131350801098190000'
    ],
    [
        '985532528', '', '', '469', '0', '2240904', '10000000', '6291456', '1880936',
        '1911608', '124320', '28709512', '604456', 'ServerManager', '31225576', '14591',
        '400', '393', '390', '388', '0', '82', '36921344', '402644992', '71295', '270884',
        '6240', '14022', '1880936', '124320', '0', '4227247572262', '131350801098190000'
    ],
    [
        '382301220888', '', '', '292', '0', '2240904', '10000000', '6291456', '827320',
        '1550080', '0', '31305288', '2979832', 'Quartal.TaskServer', '35835200', '2043',
        '60534', '6671', '648', '0', '0', '60', '42987520', '402644992', '8485',
        '49571805', '5920', '392605', '827320', '0', '0', '4227247572262',
        '131350801098190000'
    ]
]

discovery = {'': [('_Global_', 'dotnet_clrmemory_defaultlevels')]}

checks = {
    '': [
        ('_Global_', {"upper": (10.0, 15.0)}, [
            (0, 'Time in GC: 8.78%', [
                ('percent', 8.778833599942464, 10.0, 15.0, 0, 100),
            ]),
        ]),
    ],
}
