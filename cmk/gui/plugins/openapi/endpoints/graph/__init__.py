#!/usr/bin/env python3
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
"""Graphs

Graphs visible in the Checkmk user interface can also be retrieved via the
REST-API. You have to specify site, host, service and finally the graph id or metric name.
"""

from cmk.gui.plugins.metrics.graph_images import graph_spec_from_request
from cmk.gui.plugins.openapi.endpoints.graph import request_schemas, response_schemas
from cmk.gui.plugins.openapi.endpoints.graph.common import (
    graph_id_from_request,
    reorganize_response,
    reorganize_time_range,
)
from cmk.gui.plugins.openapi.restful_objects import constructors, Endpoint
from cmk.gui.plugins.openapi.utils import serve_json
from cmk.gui.raw.plugins.main_modules.registration import resolve_combined_single_metric_spec


# This is the only endpoint that is available in the raw edition
@Endpoint(
    constructors.domain_type_action_href("graph", "get"),
    "cmk/get_graph",
    method="post",
    tag_group="Monitoring",
    request_schema=request_schemas.GetSchema,
    response_schema=response_schemas.GraphCollectionSchema,
)
def get_graph(params):
    """Get a graph

    This endpoint retrieves a graph (consisting of multiple metrics) or a single metric.
    """
    body = params["body"]

    result = graph_spec_from_request(
        {
            "specification": [
                "template",
                {
                    "site": body["site"],
                    "host_name": body["host_name"],
                    "service_description": body["service_description"],
                    "graph_id": graph_id_from_request(body),
                },
            ],
            "data_range": reorganize_time_range(body["time_range"]),
            "consolidation_function": body["reduce"],
        },
        resolve_combined_single_metric_spec,
    )
    response = reorganize_response(result)
    return serve_json(response)
