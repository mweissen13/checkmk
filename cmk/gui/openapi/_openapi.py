#!/usr/bin/env python3
# Copyright (C) 2020 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import copy
from typing import Any

from openapi_spec_validator import validate_spec

from cmk.utils.site import omd_site

from cmk.gui.plugins.openapi.restful_objects import SPEC
from cmk.gui.plugins.openapi.restful_objects.decorators import Endpoint
from cmk.gui.plugins.openapi.restful_objects.endpoint_registry import ENDPOINT_REGISTRY
from cmk.gui.plugins.openapi.restful_objects.type_defs import EndpointTarget

# TODO
#   Eventually move all of SPEC stuff in here, so we have nothing statically defined.
#   This removes variation from the code.


Ident = tuple[str, str]


def generate_data(target: EndpointTarget, validate: bool = True) -> dict[str, Any]:
    endpoint: Endpoint

    methods = ["get", "put", "post", "delete"]

    def module_name(func: Any) -> str:
        return f"{func.__module__}.{func.__name__}"

    def sort_key(e: Endpoint) -> tuple[str, int, str]:
        return module_name(e.func), methods.index(e.method), e.path

    # Depends on another commit. This Any will go away.
    seen_paths = dict[Ident, Any]()

    ident: Ident
    for endpoint in sorted(ENDPOINT_REGISTRY, key=sort_key):
        if target in endpoint.blacklist_in:
            continue

        for path, operation_dict in endpoint.operation_dicts():
            ident = endpoint.method, path
            if ident in seen_paths:
                raise ValueError(
                    f"{ident} has already been defined.\n\n"
                    f"This one: {operation_dict}\n\n"
                    f"The previous one: {seen_paths[ident]}\n\n"
                )
            seen_paths[ident] = operation_dict
            SPEC.path(
                path=path,
                operations=operation_dict,
            )

    del seen_paths

    generated_spec = SPEC.to_dict()
    #   return generated_spec
    _add_cookie_auth(generated_spec)
    if not validate:
        return generated_spec

    # NOTE: deepcopy the dict because validate_spec modifies the SPEC in-place, leaving some
    # internal properties lying around, which leads to an invalid spec-file.
    check_dict = copy.deepcopy(generated_spec)
    validate_spec(check_dict)
    # NOTE: We want to modify the thing afterwards. The SPEC object would be a global reference
    # which would make modifying the spec very awkward, so we deepcopy again.
    return generated_spec


def add_once(coll: list[dict[str, Any]], to_add: dict[str, Any]) -> None:
    """Add an entry to a collection, only once.

    Examples:

        >>> l = []
        >>> add_once(l, {'foo': []})
        >>> l
        [{'foo': []}]

        >>> add_once(l, {'foo': []})
        >>> l
        [{'foo': []}]

    Args:
        coll:
        to_add:

    Returns:

    """
    if to_add in coll:
        return None

    coll.append(to_add)
    return None


def _add_cookie_auth(check_dict):
    """Add the cookie authentication schema to the SPEC.

    We do this here, because every site has a different cookie name and such can't be predicted
    before this code here actually runs.
    """
    schema_name = "cookieAuth"
    add_once(check_dict["security"], {schema_name: []})
    check_dict["components"]["securitySchemes"][schema_name] = {
        "in": "cookie",
        "name": f"auth_{omd_site()}",
        "type": "apiKey",
        "description": "Any user of Checkmk, who has already logged in, and thus got a cookie "
        "assigned, can use the REST API. Some actions may or may not succeed due "
        "to group and permission restrictions. This authentication method has the"
        "least precedence.",
    }


__all__ = ["ENDPOINT_REGISTRY", "generate_data", "add_once"]
