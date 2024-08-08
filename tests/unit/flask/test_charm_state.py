# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Flask charm state unit tests."""
import copy
import unittest.mock
from secrets import token_hex

import pytest

from paas_app_charmer.charm_state import CharmState, S3Parameters
from paas_app_charmer.exceptions import CharmConfigInvalidError
from paas_app_charmer.flask.charm import Charm, FlaskConfig

from .constants import SAML_APP_RELATION_DATA_EXAMPLE

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
        framework_config=Charm.get_framework_config(charm),
        secret_storage=SECRET_STORAGE_MOCK,
        charm=charm,
        database_requirers={},
    )
    assert charm_state.framework_config == flask_config


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
            framework_config=Charm.get_framework_config(charm),
            secret_storage=SECRET_STORAGE_MOCK,
            charm=charm,
            database_requirers={},
        )
    for config_key in charm_config:
        assert config_key in exc.value.msg


@pytest.mark.parametrize(
    "s3_connection_info, expected_s3_parameters",
    [
        pytest.param(None, None, id="empty"),
        pytest.param(
            (
                relation_data := {
                    "access-key": "access-key",
                    "secret-key": "secret-key",
                    "bucket": "bucket",
                }
            ),
            S3Parameters(**relation_data),
            id="with data",
        ),
    ],
)
def test_s3_integration(s3_connection_info, expected_s3_parameters):
    """
    arrange: Prepare charm and charm config.
    act: Create the CharmState with s3 information.
    assert: Check the S3Parameters generated are the expected ones.
    """
    config = copy.copy(DEFAULT_CHARM_CONFIG)
    config.update(config)
    charm = unittest.mock.MagicMock(config=config)
    charm_state = CharmState.from_charm(
        charm=charm,
        framework_config=Charm.get_framework_config(charm),
        framework="flask",
        secret_storage=SECRET_STORAGE_MOCK,
        database_requirers={},
        s3_connection_info=s3_connection_info,
    )
    assert charm_state.integrations
    assert charm_state.integrations.s3_parameters == expected_s3_parameters


def test_s3_integration_raises():
    """
    arrange: Prepare charm and charm config.
    act: Create the CharmState with s3 information that is invalid.
    assert: Check that CharmConfigInvalidError is raised.
    """
    config = copy.copy(DEFAULT_CHARM_CONFIG)
    config.update(config)
    charm = unittest.mock.MagicMock(config=config)
    with pytest.raises(CharmConfigInvalidError) as exc:
        charm_state = CharmState.from_charm(
            charm=charm,
            framework_config=Charm.get_framework_config(charm),
            framework="flask",
            secret_storage=SECRET_STORAGE_MOCK,
            database_requirers={},
            s3_connection_info={"bucket": "bucket"},
        )
    assert "S3" in str(exc)


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


def test_saml_integration():
    """
    arrange: Prepare charm and charm config.
    act: Create the CharmState with saml information.
    assert: Check the SamlParameters generated are the expected ones.
    """
    saml_app_relation_data = dict(SAML_APP_RELATION_DATA_EXAMPLE)
    config = copy.copy(DEFAULT_CHARM_CONFIG)
    config.update(config)
    charm = unittest.mock.MagicMock(config=config)
    charm_state = CharmState.from_charm(
        charm=charm,
        framework_config=Charm.get_framework_config(charm),
        framework="flask",
        secret_storage=SECRET_STORAGE_MOCK,
        database_requirers={},
        saml_relation_data=saml_app_relation_data,
    )
    assert charm_state.integrations
    assert charm_state.integrations.saml_parameters
    saml_parameters = charm_state.integrations.saml_parameters
    assert saml_parameters.entity_id == saml_app_relation_data["entity_id"]
    assert saml_parameters.metadata_url == saml_app_relation_data["metadata_url"]
    assert (
        saml_parameters.single_sign_on_redirect_url
        == saml_app_relation_data["single_sign_on_service_redirect_url"]
    )
    assert saml_parameters.signing_certificate == saml_app_relation_data["x509certs"].split(",")[0]


def _test_saml_integration_invalid_parameters():
    params = []
    params.append(
        pytest.param(
            {},
            ["Invalid Saml"],
            id="Empty relation data",
        )
    )
    saml_app_relation_data = dict(SAML_APP_RELATION_DATA_EXAMPLE)
    del saml_app_relation_data["single_sign_on_service_redirect_url"]
    params.append(
        pytest.param(
            saml_app_relation_data,
            ["Invalid Saml", "single_sign_on_service_redirect_url"],
            id="Missing single_sign_on_service_redirect_url",
        )
    )
    saml_app_relation_data = dict(SAML_APP_RELATION_DATA_EXAMPLE)
    del saml_app_relation_data["x509certs"]
    params.append(
        pytest.param(
            saml_app_relation_data,
            ["Invalid Saml", "x509certs"],
            id="Missing x509certs",
        )
    )
    saml_app_relation_data = dict(SAML_APP_RELATION_DATA_EXAMPLE)
    saml_app_relation_data["x509certs"] = ""
    params.append(
        pytest.param(
            saml_app_relation_data,
            ["Invalid Saml", "x509certs"],
            id="Empty x509certs",
        )
    )
    return params


@pytest.mark.parametrize(
    "saml_app_relation_data, error_messages", _test_saml_integration_invalid_parameters()
)
def test_saml_integration_invalid(saml_app_relation_data, error_messages):
    """
    arrange: Prepare a saml relation data that is invalid.
    act: Try to build CharmState.
    assert: It should raise CharmConfigInvalidError with a specific error message.
    """
    config = copy.copy(DEFAULT_CHARM_CONFIG)
    config.update(config)
    charm = unittest.mock.MagicMock(config=config)
    with pytest.raises(CharmConfigInvalidError) as exc:
        charm_state = CharmState.from_charm(
            charm=charm,
            framework_config=Charm.get_framework_config(charm),
            framework="flask",
            secret_storage=SECRET_STORAGE_MOCK,
            database_requirers={},
            saml_relation_data=saml_app_relation_data,
        )
    for message in error_messages:
        assert message in str(exc)
