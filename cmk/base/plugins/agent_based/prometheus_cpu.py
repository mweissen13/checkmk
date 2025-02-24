#!/usr/bin/env python3
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
import pydantic

from cmk.base.plugins.agent_based.agent_based_api.v1 import register, type_defs
from cmk.base.plugins.agent_based.utils import cpu


class CPULoad(pydantic.BaseModel):
    """section: prometheus_cpu_v1"""

    load1: float
    load5: float
    load15: float
    num_cpus: int


def parse(string_table: type_defs.StringTable) -> cpu.Section:
    """
    >>> parse([['{"load1": 1.06, "load5": 1.68, "load15": 1.41, "num_cpus": 8}']])
    Section(load=Load(load1=1.06, load5=1.68, load15=1.41), num_cpus=8, threads=None, type=<ProcessorType.unspecified: 0>)
    """
    parsed_section = CPULoad.parse_raw(string_table[0][0])
    return cpu.Section(
        cpu.Load(
            load1=parsed_section.load1,
            load5=parsed_section.load5,
            load15=parsed_section.load15,
        ),
        num_cpus=parsed_section.num_cpus,
    )


register.agent_section(
    name="prometheus_cpu_v1",
    parse_function=parse,
    parsed_section_name="cpu",
    supersedes=["ucd_cpu_load"],
)
