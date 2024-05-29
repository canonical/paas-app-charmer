# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integrations classes for the charm state unit tests."""

import unittest.mock

import pytest

from paas_app_charmer.integrations import DatabaseIntegration, RedisIntegration


@pytest.mark.parametrize(
    "name, redis_uri, optional, expected_env_vars, expect_blocks",
    [
        pytest.param("redis", None, False, {}, True),
        pytest.param("redis", None, True, {}, False),
        pytest.param("redis", "", False, {}, True),
        pytest.param(
            "redis",
            "redis://10.1.88.132:6379",
            False,
            {"REDIS_DB_CONNECT_STRING": "redis://10.1.88.132:6379"},
            False,
        ),
        pytest.param(
            "redis",
            "redis://10.1.88.132:6379",
            True,
            {"REDIS_DB_CONNECT_STRING": "redis://10.1.88.132:6379"},
            False,
        ),
    ],
)
def test_redis_integration(name, redis_uri, optional, expected_env_vars, expect_blocks):
    """
    arrange:
    act: Create the Redis Integration
    assert: Check the desired environment variables and if the charm should be blocked.
    """
    integration = RedisIntegration(name, redis_uri, optional)
    assert integration.name == name
    assert integration.block_charm() == expect_blocks
    assert integration.gen_environment() == expected_env_vars


@pytest.mark.parametrize(
    "name, data, optional, expected_env_vars, expected_blocks",
    [
        pytest.param(
            "mysql",
            {
                "endpoints": "test-mysql:3306",
                "password": "test-password",
                "username": "test-username",
            },
            False,
            {
                "MYSQL_DB_CONNECT_STRING": "mysql://test-username:test-password@test-mysql:3306/flask-app"
            },
            False,
        ),
        pytest.param(
            "postgresql",
            {
                "database": "test-database",
                "endpoints": "test-postgresql:5432,test-postgresql-2:5432",
                "password": "test-password",
                "username": "test-username",
            },
            False,
            {
                "POSTGRESQL_DB_CONNECT_STRING": "postgresql://test-username:test-password"
                "@test-postgresql:5432/test-database"
            },
            False,
        ),
        pytest.param(
            "mongodb",
            {"uris": "mongodb://foobar/"},
            True,
            {"MONGODB_DB_CONNECT_STRING": "mongodb://foobar/"},
            False,
        ),
        pytest.param(
            "mongodb",
            {},
            True,
            {},
            False,
        ),
        pytest.param(
            "mongodb",
            {},
            False,
            {},
            True,
        ),
    ],
)
def test_database_integration(name, data, optional, expected_env_vars, expected_blocks):
    """
    arrange: For each reasonable case.
    act: Create the Database Integration.
    assert: Check the desired environment variables and if the charm should be blocked.
    """
    # Create the databases mock with the relation data
    database_require = unittest.mock.MagicMock()
    database_require.fetch_relation_data = unittest.mock.MagicMock(return_value={"data": data})
    database_require.database = data.get("database", "flask-app")

    integration = DatabaseIntegration(name, database_require, optional)
    assert integration.name == name
    assert integration.block_charm() == expected_blocks
    assert integration.gen_environment() == expected_env_vars
