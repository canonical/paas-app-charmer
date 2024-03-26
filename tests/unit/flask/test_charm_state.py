# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Flask charm state unit tests."""
import copy
import unittest.mock

import pytest

from paas_app_charmer._gunicorn.charm_state import CharmState
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
