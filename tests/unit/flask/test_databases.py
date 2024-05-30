# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Flask charm database relations unit tests."""

import unittest.mock

import pytest

from paas_app_charmer.databases import get_uris

DATABASE_URL_TEST_PARAMS = [
    (
        (
            {
                "interface": "mysql",
                "data": {
                    "endpoints": "test-mysql:3306",
                    "password": "test-password",
                    "username": "test-username",
                },
            },
        ),
        {
            "MYSQL_DB_CONNECT_STRING": (
                "mysql://test-username:test-password@test-mysql:3306/flask-app"
            )
        },
    ),
    (
        (
            {
                "interface": "postgresql",
                "data": {
                    "database": "test-database",
                    "endpoints": "test-postgresql:5432,test-postgresql-2:5432",
                    "password": "test-password",
                    "username": "test-username",
                },
            },
        ),
        {
            "POSTGRESQL_DB_CONNECT_STRING": (
                "postgresql://test-username:test-password" "@test-postgresql:5432/test-database"
            )
        },
    ),
    (
        ({"interface": "mongodb", "data": {"uris": "mongodb://foobar/"}},),
        {"MONGODB_DB_CONNECT_STRING": "mongodb://foobar/"},
    ),
    (
        (
            {
                "interface": "mysql",
                "data": {
                    "endpoints": "test-mysql:3306",
                    "password": "test-password",
                    "username": "test-username",
                },
            },
            {
                "interface": "postgresql",
                "data": {
                    "database": "test-database",
                    "endpoints": "test-postgresql:5432,test-postgresql-2:5432",
                    "password": "test-password",
                    "username": "test-username",
                },
            },
        ),
        {
            "MYSQL_DB_CONNECT_STRING": (
                "mysql://test-username:test-password@test-mysql:3306/flask-app"
            ),
            "POSTGRESQL_DB_CONNECT_STRING": (
                "postgresql://test-username:test-password" "@test-postgresql:5432/test-database"
            ),
        },
    ),
]


@pytest.mark.parametrize("relations, expected_output", DATABASE_URL_TEST_PARAMS)
def test_database_uri_mocked(
    relations: tuple,
    expected_output: dict,
) -> None:
    """
    arrange: none
    act: start the flask charm, set flask-app container to be ready and relate it to the db.
    assert: get_uris() should return the correct databaseURI dict
    """
    # Create the databases mock with the relation data
    _databases = {}
    for relation in relations:
        interface = relation["interface"]
        database_require = unittest.mock.MagicMock()
        database_require.relation_name = interface
        database_require.fetch_relation_data = unittest.mock.MagicMock(
            return_value={"data": relation["data"]}
        )
        database_require.database = relation["data"].get("database", "flask-app")
        _databases[interface] = database_require

    assert get_uris(_databases) == expected_output
