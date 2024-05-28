# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Flask charm unit tests."""

# this is a unit test file
# pylint: disable=protected-access

import unittest.mock

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


def test_working_integrations(harness: Harness):
    """
    arrange: Prepare a Redis and a database integration.
    act: Start the flask charm and set flask-app container to be ready.
    assert: The flask service should have the Redis and the
        database environment variables in its plan.
    """
    # The relations have to be created before the charm, as
    # this is a problem with ops.testing, as the charm __init__ only
    # runs once on the beginning.
    redis_relation_data = {
        "hostname": "10.1.88.132",
        "port": "6379",
    }
    harness.add_relation("redis", "redis-k8s", unit_data=redis_relation_data)

    postgresql_relation_data = {
        "database": "test-database",
        "endpoints": "test-postgresql:5432,test-postgresql-2:5432",
        "password": "test-password",
        "username": "test-username",
    }
    harness.add_relation("postgresql", "postgresql-k8s", app_data=postgresql_relation_data)

    harness.set_leader(True)
    harness.begin_with_initial_hooks()

    container = harness.charm.unit.get_container(FLASK_CONTAINER_NAME)
    container.add_layer("a_layer", DEFAULT_LAYER)

    # The charm_state has to be reconstructed here because at this point
    # the data in the relations can be different than what was in charm.__init__
    # when the charm was initialised.
    new_charm_state = harness.charm._build_charm_state()
    harness.charm._charm_state = new_charm_state
    harness.charm._wsgi_app._charm_state = new_charm_state
    harness.container_pebble_ready(FLASK_CONTAINER_NAME)
    container = harness.charm.unit.get_container(FLASK_CONTAINER_NAME)

    assert harness.model.unit.status == ops.ActiveStatus()
    service_env = container.get_plan().services["flask"].environment
    assert service_env["REDIS_DB_CONNECT_STRING"] == "redis://10.1.88.132:6379"
    assert (
        service_env["POSTGRESQL_DB_CONNECT_STRING"]
        == "postgresql://test-username:test-password@test-postgresql:5432/test-database"
    )


def test_optional_integration_blocks_charm(harness: Harness):
    """
    arrange: Set the Redis integration as not optional.
    act: Start the flask charm and set flask-app container to be ready.
    assert: The flask service should be blocked, as it does
        not have an integration with Redis.
    """

    harness.framework.meta.requires["redis"].optional = False
    harness.set_leader(True)
    harness.begin_with_initial_hooks()

    container = harness.charm.unit.get_container(FLASK_CONTAINER_NAME)
    container.add_layer("a_layer", DEFAULT_LAYER)

    # The charm_state has to be reconstructed here because at this point
    # the connection data can be different as it was in charm.__init__
    # when the charm was initialised the first time. In particular in this
    # case, the peer relation is not ready.
    new_charm_state = harness.charm._build_charm_state()
    harness.charm._charm_state = new_charm_state
    harness.charm._wsgi_app._charm_state = new_charm_state

    harness.container_pebble_ready(FLASK_CONTAINER_NAME)
    container = harness.charm.unit.get_container(FLASK_CONTAINER_NAME)

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "redis" in str(harness.model.unit.status.message)


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
