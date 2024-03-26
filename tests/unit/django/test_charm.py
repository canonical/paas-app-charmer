# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Flask charm unit tests."""

# this is a unit test file
# pylint: disable=protected-access

import unittest.mock

import pytest
from ops.testing import Harness

from paas_app_charmer._gunicorn.charm_state import CharmState
from paas_app_charmer._gunicorn.webserver import GunicornWebserver
from paas_app_charmer._gunicorn.wsgi_app import WsgiApp

from .constants import DEFAULT_LAYER

TEST_DJANGO_CONFIG_PARAMS = [
    pytest.param({}, {"DJANGO_SECRET_KEY": "test", "DJANGO_ALLOWED_HOSTS": "[]"}, id="default"),
    pytest.param(
        {"django-allowed-hosts": "test.local"},
        {"DJANGO_SECRET_KEY": "test", "DJANGO_ALLOWED_HOSTS": '["test.local"]'},
        id="allowed-hosts",
    ),
    pytest.param(
        {"django-debug": True},
        {"DJANGO_SECRET_KEY": "test", "DJANGO_ALLOWED_HOSTS": "[]", "DJANGO_DEBUG": "true"},
        id="debug",
    ),
    pytest.param(
        {"django-secret-key": "foobar"},
        {"DJANGO_SECRET_KEY": "foobar", "DJANGO_ALLOWED_HOSTS": "[]"},
        id="secret-key",
    ),
]


@pytest.mark.parametrize("config, env", TEST_DJANGO_CONFIG_PARAMS)
def test_django_config(harness: Harness, config: dict, env: dict) -> None:
    """
    arrange: none
    act: start the django charm and set django-app container to be ready.
    assert: flask charm should submit the correct flaks pebble layer to pebble.
    """
    harness.begin()
    container = harness.charm.unit.get_container("django-app")
    # ops.testing framework apply layers by label in lexicographical order...
    container.add_layer("a_layer", DEFAULT_LAYER)
    secret_storage = unittest.mock.MagicMock()
    secret_storage.is_secret_storage_ready = True
    secret_storage.get_secret_key.return_value = "test"
    harness.update_config(config)
    charm_state = CharmState.from_charm(
        framework="django",
        wsgi_config=harness.charm.get_wsgi_config(),
        charm=harness.charm,
        secret_storage=secret_storage,
        database_requirers={},
    )
    webserver = GunicornWebserver(
        charm_state=charm_state,
        container=container,
    )
    django_app = WsgiApp(
        container=harness.charm.unit.get_container("django-app"),
        charm_state=charm_state,
        webserver=webserver,
        database_migration=harness.charm._database_migration,
    )
    django_app.restart()
    plan = container.get_plan()
    django_layer = plan.to_dict()["services"]["django"]
    assert django_layer == {
        "environment": env,
        "override": "replace",
        "startup": "enabled",
        "command": "/bin/python3 -m gunicorn -c /django/gunicorn.conf.py django_app.wsgi:application",
        "after": ["statsd-exporter"],
        "user": "_daemon_",
    }
