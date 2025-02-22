#!/usr/bin/env python3
# Copyright (C) 2020 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import json

import pytest

from tests.unit.cmk.gui.conftest import WebTestAppForCMK

from cmk.utils.livestatus_helpers.testing import MockLiveStatusConnection

GRAPH_ENDPOINT_GET = "/NO_SITE/check_mk/api/1.0/domain-types/graph/actions/get/invoke"


@pytest.mark.usefixtures("with_host")
def test_openapi_get_graph_graph(
    aut_user_auth_wsgi_app: WebTestAppForCMK, mock_livestatus: MockLiveStatusConnection
) -> None:
    mock_livestatus.set_sites(["NO_SITE"])
    mock_livestatus.add_table(
        "services",
        [
            {
                "check_command": "check_mk-cpu_loads",
                "service_description": "CPU load",
                "host_name": "heute",
                "metrics": [
                    "load1"
                ],  # please don't add another metric, it might make the test non-deterministic
                "perf_data": "load1=2.22;;;0;8",
            }
        ],
    )
    mock_livestatus.expect_query(
        # hostfield with should_be_monitored=True
        "GET hosts\nColumns: name\nFilter: name = heute"
    )
    mock_livestatus.expect_query(
        "GET services\nColumns: perf_data metrics check_command\nFilter: host_name = heute\nFilter: service_description = CPU load\nColumnHeaders: off"
    )
    mock_livestatus.expect_query(
        "GET services\nColumns: rrddata:load1:load1.average:0.0:30.0:60\nFilter: host_name = heute\nFilter: service_description = CPU load\nColumnHeaders: off"
    )
    with mock_livestatus():
        resp = aut_user_auth_wsgi_app.post(
            url=GRAPH_ENDPOINT_GET,
            content_type="application/json",
            headers={"Accept": "application/json"},
            status=200,
            params=json.dumps(
                {
                    "site": "NO_SITE",
                    "host_name": "heute",
                    "service_description": "CPU load",
                    "type": "graph",
                    "graph_id": "cpu_load",
                    "time_range": {"start": "1970-01-01T00:00:00Z", "end": "1970-01-01T00:00:30Z"},
                }
            ),
        )
    expected = {
        "metrics": [
            {
                "color": "#00d1ff",
                "line_type": "area",
                "data_points": [None],
                "title": "CPU load average of last minute",
            }
        ],
        "step": 60,
        "time_range": {"end": "1970-01-01T00:01:00+00:00", "start": "1970-01-01T00:00:00+00:00"},
    }
    assert resp.json == expected


@pytest.mark.usefixtures("with_host")
def test_openapi_get_graph_metric(
    aut_user_auth_wsgi_app: WebTestAppForCMK, mock_livestatus: MockLiveStatusConnection
) -> None:
    mock_livestatus.set_sites(["NO_SITE"])
    mock_livestatus.add_table(
        "services",
        [
            {
                "check_command": "check_mk-cpu_loads",
                "service_description": "CPU load",
                "host_name": "heute",
                "metrics": ["load1"],
                "perf_data": "load1=2.22;;;0;8",
            }
        ],
    )
    mock_livestatus.expect_query(
        # hostfield with should_be_monitored=True
        "GET hosts\nColumns: name\nFilter: name = heute"
    )
    mock_livestatus.expect_query(
        "GET services\nColumns: perf_data metrics check_command\nFilter: host_name = heute\nFilter: service_description = CPU load\nColumnHeaders: off"
    )
    mock_livestatus.expect_query(
        "GET services\nColumns: rrddata:load1:load1.average:1.0:2.0:60\nFilter: host_name = heute\nFilter: service_description = CPU load\nColumnHeaders: off"
    )
    with mock_livestatus():
        resp = aut_user_auth_wsgi_app.post(
            url=GRAPH_ENDPOINT_GET,
            content_type="application/json",
            headers={"Accept": "application/json"},
            status=200,
            params=json.dumps(
                {
                    "site": "NO_SITE",
                    "host_name": "heute",
                    "service_description": "CPU load",
                    "metric_id": "load1",
                    "type": "single_metric",
                    "time_range": {"start": "1970-01-01T00:00:01Z", "end": "1970-01-01T00:00:02Z"},
                }
            ),
        )
    expected = {
        "metrics": [
            {
                "color": "#00d1ff",
                "line_type": "area",
                "data_points": [None],
                "title": "CPU load average of last minute",
            }
        ],
        "step": 60,
        "time_range": {"end": "1970-01-01T00:01:00+00:00", "start": "1970-01-01T00:00:00+00:00"},
    }
    assert resp.json == expected
