# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Flask charm unit tests."""

# this is a unit test file
# pylint: disable=protected-access

import unittest.mock
from secrets import token_hex

import ops
from ops.testing import Harness

from paas_app_charmer._gunicorn.charm_state import CharmState
from paas_app_charmer._gunicorn.webserver import GunicornWebserver
from paas_app_charmer._gunicorn.wsgi_app import WsgiApp
from paas_app_charmer.flask import Charm

from .constants import DEFAULT_LAYER, FLASK_CONTAINER_NAME


def test_flask_pebble_layer(harness: Harness) -> None:
    """
    arrange: none
    act: start the flask charm and set flask-app container to be ready.
    assert: flask charm should submit the correct flaks pebble layer to pebble.
    """
    harness.begin()
    container = harness.charm.unit.get_container(FLASK_CONTAINER_NAME)
    # ops.testing framework apply layers by label in lexicographical order...
    container.add_layer("a_layer", DEFAULT_LAYER)
    secret_storage = unittest.mock.MagicMock()
    secret_storage.is_initialized = True
    test_key = "0" * 16
    secret_storage.get_secret_key.return_value = test_key
    charm_state = CharmState.from_charm(
        wsgi_config=Charm.get_wsgi_config(harness.charm),
        charm=harness.charm,
        framework="flask",
        secret_storage=secret_storage,
        database_requirers={},
    )
    webserver = GunicornWebserver(
        charm_state=charm_state,
        container=container,
    )
    flask_app = WsgiApp(
        container=container,
        charm_state=charm_state,
        webserver=webserver,
        database_migration=harness.charm._database_migration,
    )
    flask_app.restart()
    plan = container.get_plan()
    flask_layer = plan.to_dict()["services"]["flask"]
    assert flask_layer == {
        "environment": {
            "FLASK_PREFERRED_URL_SCHEME": "HTTPS",
            "FLASK_SECRET_KEY": "0000000000000000",
        },
        "override": "replace",
        "startup": "enabled",
        "command": f"/bin/python3 -m gunicorn -c /flask/gunicorn.conf.py app:app",
        "after": ["statsd-exporter"],
        "user": "_daemon_",
    }


def test_s3_integration(harness: Harness):
    """TODO."""
    # Unfortunately the s3 relation has to be created before the charm,
    # this is a problem with ops.testing, as the charm __init__ only
    # runs once on the beginning. For a similar reason, the
    # charm_state has to be reconstructed :(
    s3_relation_data = {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
        "bucket": "flask-bucket",
        "path": "/whatever",
        "s3-uri-style": "path",
        "endpoint": "https://s3.example.com",
    }
    harness.add_relation("s3", "s3-integrator", app_data=s3_relation_data)
    harness.set_leader(True)
    harness.begin_with_initial_hooks()

    container = harness.charm.unit.get_container(FLASK_CONTAINER_NAME)
    container.add_layer("a_layer", DEFAULT_LAYER)

    new_charm_state = harness.charm._build_charm_state()
    harness.charm._charm_state = new_charm_state
    harness.charm._wsgi_app._charm_state = new_charm_state
    harness.container_pebble_ready(FLASK_CONTAINER_NAME)
    container = harness.charm.unit.get_container(FLASK_CONTAINER_NAME)

    assert harness.model.unit.status == ops.ActiveStatus()
    service_env = container.get_plan().services["flask"].environment
    assert service_env["S3_BUCKET"] == "flask-bucket"
    assert service_env["S3_ACCESS_KEY"] == s3_relation_data["access-key"]


def test_rotate_secret_key_action(harness: Harness):
    """
    arrange: none
    act: invoke the rotate-secret-key callback function
    assert: the action should change the secret key value in the relation data and restart the
        flask application with the new secret key.
    """
    harness.begin_with_initial_hooks()
    action_event = unittest.mock.MagicMock()
    secret_key = harness.get_relation_data(0, harness.charm.app)["flask_secret_key"]
    assert secret_key
    harness.charm._on_rotate_secret_key_action(action_event)
    new_secret_key = harness.get_relation_data(0, harness.charm.app)["flask_secret_key"]
    assert secret_key != new_secret_key
