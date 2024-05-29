# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integrations classes for the charm state unit tests."""

import unittest.mock
from secrets import token_hex

import pytest

from paas_app_charmer.integrations import (
    DatabaseIntegration,
    RedisIntegration,
    S3Integration,
    S3Parameters,
)


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


@pytest.mark.parametrize(
    "name, s3_connection_info, optional, expected_env_vars, expected_blocks",
    [
        pytest.param(
            "s3",
            {},
            False,
            {},
            True,
        ),
        pytest.param(
            "s3",
            {},
            True,
            {},
            False,
        ),
        pytest.param(
            "s3",
            {
                "bucket": "backup-bucket",
            },
            False,
            {},
            True,
        ),
        pytest.param(
            "s3",
            {
                "bucket": "backup-bucket",
                "secret-key": "key",
                "access-key": "access",
            },
            False,
            {
                "S3_ACCESS_KEY": "access",
                "S3_BUCKET": "backup-bucket",
                "S3_SECRET_KEY": "key",
            },
            False,
        ),
        pytest.param(
            "s3",
            {
                "access-key": "access-key",
                "secret-key": "secret-key",
                "bucket": "example-bucket",
                "endpoint": "https://s3.example.com",
                "path": "storage",
                "region": "us-east-1",
                "s3-api-version": "s3v4",
                "s3-uri-style": "path",
                "storage-class": "GLACIER",
                "tls-ca-chain": """-----BEGIN CERTIFICATE-----
MIIDOzCCAiOgAwIBAgIUFrWP+9/yAfKCJ4wt+8G16Z00NwcwDQYJKoZIhvcNAQEL
BQAwLTELMAkGA1UEBhMCVVMxHjAcBgNVBAMMFXJvb3RjYS55b3VyZG9tYWluLmNv
bTAeFw0yMjA3MDYxNTIwMjhaFw0zMjA3MDMxNTIwMjhaMC0xCzAJBgNVBAYTAlVT
MR4wHAYDVQQDDBVyb290Y2EueW91cmRvbWFpbi5jb20wggEiMA0GCSqGSIb3DQEB
AQUAA4IBDwAwggEKAoIBAQCChauUqFfey9B3JyRZOxH1T8LkeCgzBgQwfCpNAoKo
xVhZbquBBxx2YAM5jgLkIvGnZQ2yaZ94c/R9GeTeKJt4jYPj+Qxevt0Wg2Q4jBQW
eAl+cBiq9uC9kpyv+/G7SJtItRBBcwtEznaGfN3ZQvHlxzRWH3alFo1iwc6E9IwZ
EQKkVW1bkdN4a+W7Sr670nBvGfVZCDLoH0P4uKmbcCFo7aeuJt4GJlcK6UfCiBBB
QIJDgF4HfOeBC/2UeZGHIOBxzYsq6m8dfCLGofglb6uaAeUB+6Q5wHQ4CTeWzpds
9OyTKwjsFKCSnpUkWFZCslbf4X61/pgkv1ZEuxLRFGMTAgMBAAGjUzBRMB0GA1Ud
DgQWBBR26Cx527A2QEnuF5l/YPGu22oBQzAfBgNVHSMEGDAWgBR26Cx527A2QEnu
F5l/YPGu22oBQzAPBgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQA5
r3s8sqHH9gsqW83OX0cJFP4skqsP/QEb2Q0iPGjh3srXRQn4UtY1/5Ti37+XRVE2
7QnBEJ+FJYVCc9+R4KRsCi77jUgugBa6+GJ6kLPkCpzbg9qGoaTxbBhpEbbnNFK8
hre4I4VKNrjXPyxZ02JgvAEpU6dYoEBvuVNBBuIZkXCGC9zFmSAnx8lQhldE04d8
HYDfiasYMLKjTzLQmWGMWeo7tQyDBeCuKgcrpusGTE7y6ohj+w5MxcGoBRRPZ3jh
YegJBk9w6phj73tzMBuj5qIvVCTG2/BF2f6Artk43s9tx1PXAj03hplW8i7XB3ua
eTqJHx5C3sUyBKoieXJq
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIIDnTCCAoWgAwIBAgIUGlm3wXnLUA/o4F4b/jr17cgeOKwwDQYJKoZIhvcNAQEL
BQAwLTELMAkGA1UEBhMCVVMxHjAcBgNVBAMMFXJvb3RjYS55b3VyZG9tYWluLmNv
bTAeFw0yMjA3MDYxNTIwMjhaFw0yNDEwMDgxNTIwMjhaMCgxCzAJBgNVBAYTAlVT
MRkwFwYDVQQDDBAqLnlvdXJkb21haW4uY29tMIIBIjANBgkqhkiG9w0BAQEFAAOC
AQ8AMIIBCgKCAQEAplmwyXOi/0Ljwwx7LPCv3xT2EZ1ngKyBlGn8iD+YgxynMr46
KiwhS8Mbj0WCo7tx3dTZAtTUd/p+dfmpqphhv1nq/im5g3lAMeIQd8cgUtcJqrpi
FQvor1Bm1qF6Y1q4pA4EOxyDhejjLVtcn0xYZxB7BYTRp1L9ZK0qv/fdwCs0TQwq
uObSiMIQxvuGEnCw5dN0BUnqZ0juBUQFMT2Z3RFSNx0vXJW+4z10Nwz4D0fRUkXV
n6TrWu/M3osvGLjNqmYQ6owV2wQlOy5b5cUfa1vcS0brhSd3E7w9fhYwXAD47vhF
jncub9knNahZRSzSLfUB+1MzADNCWx9OwTJpTQIDAQABo4G5MIG2MAkGA1UdEwQC
MAAwaQYDVR0RBGIwYIIQKi55b3VyZG9tYWluLmNvbYIUKi5ubXMueW91cmRvbWFp
bi5jb22CGCouc3RhZ2luZy55b3VyZG9tYWluLmNvbYIcKi5ubXMuc3RhZ2luZy55
b3VyZG9tYWluLmNvbTAdBgNVHQ4EFgQUxzl/AEaI47LsJwnJINk4ZLOZcNswHwYD
VR0jBBgwFoAUdugseduwNkBJ7heZf2DxrttqAUMwDQYJKoZIhvcNAQELBQADggEB
AACEEv0giGxus/Bwtnb3pGKa5mu7bQPamT0DhBq6qwl8xPp6dP93tDJaF8QaKHMq
54TvOPTWLFVOMJQZJDlBVyEjB8NrQeiZZiXPVgPTyiT5DmArO5fCsqB7JvPZqM2K
fd1ftXRpxKxzTNzpLUvcjbkLuaAlXaEUU/bu5XSYhUxxcDdCoxlVoBE3rNJOCAdX
QIRYjBWEvjWyX5ZT1oNIJK2QO+dbafwpXWs6WITt5BPO9k/sbkBJhA8ztxofEBr0
EANWJ/0DpvCzOqbdsBDYpceQjbTwYl9lMLP+3b8TC52E/dseEmKlHahF+K6dlp99
UBwM4xo+z6onwTr+vUfXNHI=
-----END CERTIFICATE-----""",
            },
            False,
            {
                "S3_ACCESS_KEY": "access-key",
                "S3_ADDRESSING_STYLE": "path",
                "S3_API_VERSION": "s3v4",
                "S3_BUCKET": "example-bucket",
                "S3_ENDPOINT": "https://s3.example.com",
                "S3_PATH": "storage",
                "S3_REGION": "us-east-1",
                "S3_SECRET_KEY": "secret-key",
                "S3_STORAGE_CLASS": "GLACIER",
                "S3_URI_STYLE": "path",
                "S3_TLS_CA_CHAIN": """-----BEGIN CERTIFICATE-----
MIIDOzCCAiOgAwIBAgIUFrWP+9/yAfKCJ4wt+8G16Z00NwcwDQYJKoZIhvcNAQEL
BQAwLTELMAkGA1UEBhMCVVMxHjAcBgNVBAMMFXJvb3RjYS55b3VyZG9tYWluLmNv
bTAeFw0yMjA3MDYxNTIwMjhaFw0zMjA3MDMxNTIwMjhaMC0xCzAJBgNVBAYTAlVT
MR4wHAYDVQQDDBVyb290Y2EueW91cmRvbWFpbi5jb20wggEiMA0GCSqGSIb3DQEB
AQUAA4IBDwAwggEKAoIBAQCChauUqFfey9B3JyRZOxH1T8LkeCgzBgQwfCpNAoKo
xVhZbquBBxx2YAM5jgLkIvGnZQ2yaZ94c/R9GeTeKJt4jYPj+Qxevt0Wg2Q4jBQW
eAl+cBiq9uC9kpyv+/G7SJtItRBBcwtEznaGfN3ZQvHlxzRWH3alFo1iwc6E9IwZ
EQKkVW1bkdN4a+W7Sr670nBvGfVZCDLoH0P4uKmbcCFo7aeuJt4GJlcK6UfCiBBB
QIJDgF4HfOeBC/2UeZGHIOBxzYsq6m8dfCLGofglb6uaAeUB+6Q5wHQ4CTeWzpds
9OyTKwjsFKCSnpUkWFZCslbf4X61/pgkv1ZEuxLRFGMTAgMBAAGjUzBRMB0GA1Ud
DgQWBBR26Cx527A2QEnuF5l/YPGu22oBQzAfBgNVHSMEGDAWgBR26Cx527A2QEnu
F5l/YPGu22oBQzAPBgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQA5
r3s8sqHH9gsqW83OX0cJFP4skqsP/QEb2Q0iPGjh3srXRQn4UtY1/5Ti37+XRVE2
7QnBEJ+FJYVCc9+R4KRsCi77jUgugBa6+GJ6kLPkCpzbg9qGoaTxbBhpEbbnNFK8
hre4I4VKNrjXPyxZ02JgvAEpU6dYoEBvuVNBBuIZkXCGC9zFmSAnx8lQhldE04d8
HYDfiasYMLKjTzLQmWGMWeo7tQyDBeCuKgcrpusGTE7y6ohj+w5MxcGoBRRPZ3jh
YegJBk9w6phj73tzMBuj5qIvVCTG2/BF2f6Artk43s9tx1PXAj03hplW8i7XB3ua
eTqJHx5C3sUyBKoieXJq
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIIDnTCCAoWgAwIBAgIUGlm3wXnLUA/o4F4b/jr17cgeOKwwDQYJKoZIhvcNAQEL
BQAwLTELMAkGA1UEBhMCVVMxHjAcBgNVBAMMFXJvb3RjYS55b3VyZG9tYWluLmNv
bTAeFw0yMjA3MDYxNTIwMjhaFw0yNDEwMDgxNTIwMjhaMCgxCzAJBgNVBAYTAlVT
MRkwFwYDVQQDDBAqLnlvdXJkb21haW4uY29tMIIBIjANBgkqhkiG9w0BAQEFAAOC
AQ8AMIIBCgKCAQEAplmwyXOi/0Ljwwx7LPCv3xT2EZ1ngKyBlGn8iD+YgxynMr46
KiwhS8Mbj0WCo7tx3dTZAtTUd/p+dfmpqphhv1nq/im5g3lAMeIQd8cgUtcJqrpi
FQvor1Bm1qF6Y1q4pA4EOxyDhejjLVtcn0xYZxB7BYTRp1L9ZK0qv/fdwCs0TQwq
uObSiMIQxvuGEnCw5dN0BUnqZ0juBUQFMT2Z3RFSNx0vXJW+4z10Nwz4D0fRUkXV
n6TrWu/M3osvGLjNqmYQ6owV2wQlOy5b5cUfa1vcS0brhSd3E7w9fhYwXAD47vhF
jncub9knNahZRSzSLfUB+1MzADNCWx9OwTJpTQIDAQABo4G5MIG2MAkGA1UdEwQC
MAAwaQYDVR0RBGIwYIIQKi55b3VyZG9tYWluLmNvbYIUKi5ubXMueW91cmRvbWFp
bi5jb22CGCouc3RhZ2luZy55b3VyZG9tYWluLmNvbYIcKi5ubXMuc3RhZ2luZy55
b3VyZG9tYWluLmNvbTAdBgNVHQ4EFgQUxzl/AEaI47LsJwnJINk4ZLOZcNswHwYD
VR0jBBgwFoAUdugseduwNkBJ7heZf2DxrttqAUMwDQYJKoZIhvcNAQELBQADggEB
AACEEv0giGxus/Bwtnb3pGKa5mu7bQPamT0DhBq6qwl8xPp6dP93tDJaF8QaKHMq
54TvOPTWLFVOMJQZJDlBVyEjB8NrQeiZZiXPVgPTyiT5DmArO5fCsqB7JvPZqM2K
fd1ftXRpxKxzTNzpLUvcjbkLuaAlXaEUU/bu5XSYhUxxcDdCoxlVoBE3rNJOCAdX
QIRYjBWEvjWyX5ZT1oNIJK2QO+dbafwpXWs6WITt5BPO9k/sbkBJhA8ztxofEBr0
EANWJ/0DpvCzOqbdsBDYpceQjbTwYl9lMLP+3b8TC52E/dseEmKlHahF+K6dlp99
UBwM4xo+z6onwTr+vUfXNHI=
-----END CERTIFICATE-----""",
            },
            False,
        ),
    ],
)
def test_s3_integration(name, s3_connection_info, optional, expected_env_vars, expected_blocks):
    """
    arrange: For each reasonable case.
    act: Create the S3 Integration.
    assert: Check the desired environment variables and if the charm should be blocked.
    """
    integration = S3Integration(name, s3_connection_info, optional)
    assert integration.name == name
    assert integration.gen_environment() == expected_env_vars
    assert integration.block_charm() == expected_blocks


@pytest.mark.parametrize(
    "s3_uri_style, addressing_style",
    [("host", "virtual"), ("path", "path"), (None, None)],
)
def test_s3_addressing_style(s3_uri_style, addressing_style) -> None:
    """
    arrange: Create s3 relation data with different s3_uri_styles.
    act: Create S3Parameters pydantic BaseModel from relation data.
    assert: Check that s3_uri_style is a valid addressing style.
    """
    s3_relation_data = {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
        "bucket": "backup-bucket",
        "region": "us-west-2",
        "s3-uri-style": s3_uri_style,
    }
    s3_parameters = S3Parameters(**s3_relation_data)
    assert s3_parameters.addressing_style == addressing_style
