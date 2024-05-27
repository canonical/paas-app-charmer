# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Flask charm state unit tests."""
import copy
import unittest.mock
from secrets import token_hex

import pydantic
import pytest

from paas_app_charmer._gunicorn.charm_state import CharmState, S3Parameters
from paas_app_charmer.exceptions import CharmConfigInvalidError
from paas_app_charmer.flask.charm import Charm, FlaskConfig

# this is a unit test file
# pylint: disable=protected-access

DEFAULT_CHARM_CONFIG = {"webserver-wsgi-path": "app:app", "flask-preferred-url-scheme": "HTTPS"}
SECRET_STORAGE_MOCK = unittest.mock.MagicMock(is_initialized=True)
SECRET_STORAGE_MOCK.get_secret_key.return_value = ""

CHARM_STATE_FLASK_CONFIG_TEST_PARAMS = [
    pytest.param(
        {"flask-env": "prod"}, {"env": "prod", "preferred_url_scheme": "HTTPS"}, id="env"
    ),
    pytest.param(
        {"flask-debug": True}, {"debug": True, "preferred_url_scheme": "HTTPS"}, id="debug"
    ),
    pytest.param(
        {"flask-secret-key": "1234"},
        {"secret_key": "1234", "preferred_url_scheme": "HTTPS"},
        id="secret-key",
    ),
    pytest.param(
        {"flask-preferred-url-scheme": "http"},
        {"preferred_url_scheme": "HTTP"},
        id="preferred-url-scheme",
    ),
]


@pytest.mark.parametrize("charm_config, flask_config", CHARM_STATE_FLASK_CONFIG_TEST_PARAMS)
def test_charm_state_flask_config(charm_config: dict, flask_config: dict) -> None:
    """
    arrange: none
    act: set flask_* charm configurations.
    assert: flask_config in the charm state should reflect changes in charm configurations.
    """
    config = copy.copy(DEFAULT_CHARM_CONFIG)
    config.update(charm_config)
    charm = unittest.mock.MagicMock(config=config)
    charm_state = CharmState.from_charm(
        framework="flask",
        wsgi_config=Charm.get_wsgi_config(charm),
        secret_storage=SECRET_STORAGE_MOCK,
        charm=charm,
        database_requirers={},
    )
    assert charm_state.wsgi_config == flask_config


@pytest.mark.parametrize(
    "charm_config",
    [
        pytest.param({"flask-env": ""}, id="env"),
        pytest.param({"flask-secret-key": ""}, id="secret-key"),
        pytest.param(
            {"flask-preferred-url-scheme": "tls"},
            id="preferred-url-scheme",
        ),
    ],
)
def test_charm_state_invalid_flask_config(charm_config: dict) -> None:
    """
    arrange: none
    act: set flask_* charm configurations to be invalid values.
    assert: the CharmState should raise a CharmConfigInvalidError exception
    """
    config = copy.copy(DEFAULT_CHARM_CONFIG)
    config.update(charm_config)
    charm = unittest.mock.MagicMock(config=config)
    with pytest.raises(CharmConfigInvalidError) as exc:
        CharmState.from_charm(
            wsgi_config=Charm.get_wsgi_config(charm),
            secret_storage=SECRET_STORAGE_MOCK,
            charm=charm,
            database_requirers={},
        )
    for config_key in charm_config:
        assert config_key in exc.value.msg


@pytest.mark.parametrize(
    "s3_connection_info, s3_parameters",
    [
        pytest.param(None, None),
        pytest.param({"bucket": "bucket-name"}, None),
        pytest.param(
            {"bucket": "bucket-name", "access-key": "id", "secret-key": "key"},
            S3Parameters(**{"bucket": "bucket-name", "access-key": "id", "secret-key": "key"}),
        ),
    ],
)
def test_charm_state_s3_parameters(s3_connection_info, s3_parameters) -> None:
    """
    arrange: TODO
    act: TODO
    assert: TODO
    """
    config = copy.copy(DEFAULT_CHARM_CONFIG)
    charm = unittest.mock.MagicMock(config=config)
    charm_state = CharmState.from_charm(
        wsgi_config=Charm.get_wsgi_config(charm),
        secret_storage=SECRET_STORAGE_MOCK,
        framework="flask",
        charm=charm,
        database_requirers={},
        s3_connection_info=s3_connection_info,
    )
    assert charm_state.s3_parameters == s3_parameters


@pytest.mark.parametrize(
    "s3_relation_data",
    [
        # Empty
        pytest.param({}),
        # No access-key
        pytest.param(
            {
                "secret-key": token_hex(16),
                "bucket": "backup-bucket",
                "region": "us-west-2",
                "s3-uri-style": "path",
            },
        ),
    ],
)
def test_s3_validation_error(s3_relation_data) -> None:
    """
    arrange: Create s3 relation data with missing fields.
    act: Create S3Parameters pydantic BaseModel from relation data.
    assert: Raises ValidationError because there are missing fields.
    """
    with pytest.raises(pydantic.ValidationError):
        S3Parameters(**s3_relation_data)


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


def test_s3_env_variables() -> None:
    """
    arrange: Create s3 relation data.
    act: Create S3Parameters pydantic BaseModel from relation data.
    assert: Check that we have the correct env variables.
    """
    access_key = token_hex(16)
    secret_key = token_hex(16)
    s3_relation_data = {
        "access-key": access_key,
        "secret-key": secret_key,
        "bucket": "bucket-name",
        "endpoint": "https://s3.example.com",
        "region": "us-west-2",
        "s3-uri-style": "host",
        "storage-class": "GLACIER",
        "path": "/",
        "s3-api-version": "s3v4",
    }
    s3_parameters = S3Parameters(**s3_relation_data)
    assert s3_parameters.to_env() == {
        "S3_ACCESS_KEY": access_key,
        "S3_SECRET_KEY": secret_key,
        "S3_BUCKET": "bucket-name",
        "S3_REGION": "us-west-2",
        "S3_ENDPOINT": "https://s3.example.com",
        "S3_ADDRESSING_STYLE": "virtual",
        "S3_API_VERSION": "s3v4",
        "S3_PATH": "/",
        "S3_STORAGE_CLASS": "GLACIER",
        "S3_URI_STYLE": "host",
    }


def test_s3_env_variables_with_none_fields() -> None:
    """
    arrange: Create s3 relation data with only required minimal fields.
    act: Create S3Parameters pydantic BaseModel from relation data.
    assert: Check that we have the correct env variables.
    """
    access_key = token_hex(16)
    secret_key = token_hex(16)
    s3_relation_data = {
        "access-key": access_key,
        "secret-key": secret_key,
        "bucket": "bucket-name",
    }
    s3_parameters = S3Parameters(**s3_relation_data)
    assert s3_parameters.to_env() == {
        "S3_ACCESS_KEY": access_key,
        "S3_SECRET_KEY": secret_key,
        "S3_BUCKET": "bucket-name",
    }
