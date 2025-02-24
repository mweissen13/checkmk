#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
import copy
from collections.abc import Iterable, Mapping
from typing import Any

import pytest

from cmk.utils.type_defs import UserId

from cmk.gui.type_defs import Users, UserSpec
from cmk.gui.userdb.htpasswd import HtpasswdUserConnector
from cmk.gui.userdb.saml2.connector import Connector, SAML2_CONNECTOR_TYPE


class TestConnector:
    @pytest.fixture(autouse=True)
    def patch_metadata_from_idp(self, metadata_from_idp: None) -> None:
        return metadata_from_idp

    @pytest.fixture
    def saml2_connection_id(self, raw_config: Mapping[str, Any]) -> str:
        return raw_config["id"]

    @pytest.fixture
    def users_pre_edit(self, saml2_connection_id: str) -> Users:
        return {
            UserId("Moss"): UserSpec({"connector": "htpasswd", "email": "moss@helloit.com"}),
            UserId("Roy"): UserSpec(
                {"connector": None, "email": "roy@helloit.com"}
            ),  # TODO: according to typing, connector can be None: wtf does this mean?!
            UserId("Jen"): UserSpec(
                {"email": "roy@helloit.com"}
            ),  # TODO: not sure if this is a real case
            UserId("Richmond"): UserSpec(
                {"connector": saml2_connection_id, "email": "richmond@helloit.com"}
            ),
        }

    @pytest.fixture
    def user_store(self, monkeypatch: pytest.MonkeyPatch, users_pre_edit: Users) -> Iterable[Users]:
        users = copy.deepcopy(users_pre_edit)
        # The following two functions are actually accessed via UserStore and patched for it.
        # 'save_users' will persist any changes in the corresponding file on disk but is not needed
        # for the purpose of our unit tests.
        monkeypatch.setattr("cmk.gui.userdb.store.load_users", lambda l: users)
        monkeypatch.setattr("cmk.gui.userdb.store.save_users", lambda u, n: None)
        yield users

    @pytest.fixture
    def get_connection(
        self, monkeypatch: pytest.MonkeyPatch, raw_config: Mapping[str, Any]
    ) -> None:
        saml2_connector = Connector(raw_config)
        connections = {"htpasswd": HtpasswdUserConnector({}), saml2_connector.id: saml2_connector}
        monkeypatch.setattr(
            "cmk.gui.userdb.saml2.connector.get_connection",
            lambda i: connections.get(i),  # pylint: disable=unnecessary-lambda
        )

    def test_connector_properties(self, raw_config: Mapping[str, Any]) -> None:
        connector = Connector(raw_config)
        assert connector.interface
        assert connector.type() == SAML2_CONNECTOR_TYPE
        assert connector.id == "uuid123"
        assert (
            connector.identity_provider_url()
            == "http://localhost:8080/simplesaml/saml2/idp/metadata.php"
        )

    def test_connector_is_enabled_config(self, raw_config: Mapping[str, Any]) -> None:
        config = {**raw_config, **{"disabled": False}}
        connector = Connector(config)
        assert connector.is_enabled() is True

    def test_connector_is_disabled_config(self, raw_config: Mapping[str, Any]) -> None:
        config = {**raw_config, **{"disabled": True}}
        connector = Connector(config)
        assert connector.is_enabled() is False

    def test_edit_user_creates_new_user(
        self,
        raw_config: Mapping[str, Any],
        get_connection: None,
        users_pre_edit: Users,
        user_store: Users,
    ) -> None:
        connector = Connector(raw_config)

        new_user_id = UserId("Paul")
        new_user_spec = UserSpec({"connector": connector.id})
        new_user = {new_user_id: new_user_spec}

        connector.create_and_update_user(new_user_id, new_user_spec)

        assert user_store == {**users_pre_edit, **new_user}

    def test_edit_user_creates_new_user_with_default_profile(
        self,
        raw_config: Mapping[str, Any],
        get_connection: None,
        users_pre_edit: Users,
        user_store: Users,
    ) -> None:
        connector = Connector(raw_config)

        new_user_id = UserId("Paul")

        connector.create_and_update_user(new_user_id)

        assert user_store == {
            **users_pre_edit,
            UserId("Paul"): UserSpec(
                {
                    "alias": "Paul",
                    "connector": connector.id,
                    "contactgroups": [],
                    "force_authuser": False,
                    "roles": ["user"],
                }
            ),
        }

    def test_edit_user_does_not_overwrite_existing_user_in_different_namespace(
        self,
        raw_config: Mapping[str, Any],
        get_connection: None,
        users_pre_edit: Users,
        user_store: Users,
    ) -> None:
        """Ensure SAML2 connector does not edit users that exist for a different connection (LDAP/HTPASSWD/...)."""

        connector = Connector(raw_config)

        new_user_id = UserId("Moss")

        with pytest.raises(ValueError):
            connector.create_and_update_user(new_user_id)

        assert user_store == users_pre_edit

    def test_edit_user_does_not_overwrite_user_of_None_namespace(
        self,
        raw_config: Mapping[str, Any],
        get_connection: None,
        users_pre_edit: Users,
        user_store: Users,
    ) -> None:
        connector = Connector(raw_config)

        new_user_id = UserId("Roy")

        with pytest.raises(ValueError):
            connector.create_and_update_user(new_user_id)

        assert user_store == users_pre_edit

    def test_edit_user_does_not_overwrite_user_of_missing_namespace(
        self,
        raw_config: Mapping[str, Any],
        get_connection: None,
        users_pre_edit: Users,
        user_store: Users,
    ) -> None:
        connector = Connector(raw_config)

        new_user_id = UserId("Jen")

        with pytest.raises(ValueError):
            connector.create_and_update_user(new_user_id)

        assert user_store == users_pre_edit

    def test_edit_user_updates_user_profile(
        self,
        raw_config: Mapping[str, Any],
        get_connection: None,
        users_pre_edit: Users,
        user_store: Users,
    ) -> None:
        connector = Connector(raw_config)

        user_id = UserId("Richmond")
        new_user_spec = UserSpec({"email": "richmond@hellonerds.com", "connector": connector.id})

        connector.create_and_update_user(user_id, new_user_spec)

        assert user_store == {**users_pre_edit, **{user_id: new_user_spec}}

    def test_password_is_a_locked_attribute(self, raw_config: Mapping[str, Any]) -> None:
        connector = Connector(raw_config)

        assert "password" in connector.locked_attributes()
