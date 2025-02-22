#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import pytest

from cmk.base.plugins.agent_based.agent_based_api.v1 import Result, Service, State
from cmk.base.plugins.agent_based.mssql_databases import (
    check_mssql_databases,
    discover_mssql_databases,
    parse_mssql_databases,
)


@pytest.fixture(scope="module", name="section")
def _get_section():
    return parse_mssql_databases(
        [
            ["MSSQL_MSSQL46", "CorreLog_Report_T", "ONLINE", "FULL", "0", "0"],
            ["MSSQL_MSSQL46", "master", "ONLINE", "SIMPLE", "0", "0"],
            ["MSSQL_MSSQL46", "msdb", "ONLINE", "SIMPLE", "0", "0"],
            ["MSSQL_MSSQL46", "NOC_ALARM_T", "ONLINE", "FULL", "0", "1"],
            ["MSSQL_MSSQL46", "test_autoclose", "ONLINE", "FULL", "1", "0"],
            ["MSSQL_MSSQL46", "test_autoclose", "RECOVERY", "PENDING", "FULL", "1", "0"],
            ["MSSQL_Mouse", "-", "ERROR: We are out of cheese!", "-", "-", "-"],
        ]
    )


def test_discover_mssql_databases(section) -> None:  # type:ignore[no-untyped-def]

    assert sorted(discover_mssql_databases(section), key=lambda s: s.item or "") == [
        Service(item="MSSQL_MSSQL46 CorreLog_Report_T"),
        Service(item="MSSQL_MSSQL46 NOC_ALARM_T"),
        Service(item="MSSQL_MSSQL46 master"),
        Service(item="MSSQL_MSSQL46 msdb"),
        Service(item="MSSQL_MSSQL46 test_autoclose"),
        Service(item="MSSQL_Mouse -"),
    ]


def test_check_error(section) -> None:  # type:ignore[no-untyped-def]

    assert list(check_mssql_databases("MSSQL_Mouse -", {}, section)) == [
        Result(state=State.CRIT, summary="We are out of cheese!"),
    ]


def test_check_warn_auto_shrink(section) -> None:  # type:ignore[no-untyped-def]

    assert list(check_mssql_databases("MSSQL_MSSQL46 NOC_ALARM_T", {}, section)) == [
        Result(state=State.OK, summary="Status: ONLINE"),
        Result(state=State.OK, summary="Recovery: FULL"),
        Result(state=State.OK, summary="Auto close: off"),
        Result(state=State.WARN, summary="Auto shrink: on"),
    ]
