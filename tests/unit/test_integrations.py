# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integrations classes for the charm state unit tests."""

import unittest.mock

import pytest

from paas_app_charmer.integrations import DatabaseIntegration, GenericIntegration


@pytest.mark.parametrize(
    "name, blocks, env_vars",
    [
        pytest.param("name1", True, {}),
        pytest.param("name2", False, {"var1": "val1"}),
    ],
)
def test_generic_integration(name, blocks, env_vars):
    """
    TODO. JUST CHECK WHAT GETS IN, GETS OUT
    """
    integration = GenericIntegration(name, blocks, env_vars)
    assert name == integration.name
    assert blocks == integration.block_charm()
    assert env_vars == integration.gen_environment()


@pytest.mark.parametrize(
    "interface_name, data, expected_env_vars",
    [
        pytest.param(
            "mysql",
            {
                "endpoints": "test-mysql:3306",
                "password": "test-password",
                "username": "test-username",
            },
            {
                "MYSQL_DB_CONNECT_STRING": "mysql://test-username:test-password@test-mysql:3306/flask-app"
            },
        ),
        pytest.param(
            "postgresql",
            {
                "database": "test-database",
                "endpoints": "test-postgresql:5432,test-postgresql-2:5432",
                "password": "test-password",
                "username": "test-username",
            },
            {
                "POSTGRESQL_DB_CONNECT_STRING": "postgresql://test-username:test-password"
                "@test-postgresql:5432/test-database"
            },
        ),
        pytest.param(
            "mongodb",
            {"uris": "mongodb://foobar/"},
            {"MONGODB_DB_CONNECT_STRING": "mongodb://foobar/"},
        ),
    ],
)
def test_database_integration(interface_name, data, expected_env_vars):
    """
    TODO.
    """
    # Create the databases mock with the relation data
    database_require = unittest.mock.MagicMock()
    database_require.fetch_relation_data = unittest.mock.MagicMock(return_value={"data": data})
    database_require.database = data.get("database", "flask-app")

    integration = DatabaseIntegration(interface_name, database_require)
    assert integration.name == interface_name
    # Until it is implemented
    assert integration.block_charm() == False
    assert integration.gen_environment() == expected_env_vars
