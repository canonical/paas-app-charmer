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
from paas_app_charmer._gunicorn.webserver import GunicornWebserver, WebserverConfig
from paas_app_charmer._gunicorn.workload_config import WorkloadConfig
from paas_app_charmer._gunicorn.wsgi_app import WsgiApp
from paas_app_charmer.flask import Charm

from .constants import DEFAULT_LAYER, FLASK_CONTAINER_NAME, SAML_APP_RELATION_DATA_EXAMPLE


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
    webserver_config = WebserverConfig.from_charm(harness.charm)
    workload_config = WorkloadConfig(
        framework="flask",
    )
    webserver = GunicornWebserver(
        webserver_config=webserver_config,
        workload_config=workload_config,
        container=container,
    )
    flask_app = WsgiApp(
        container=container,
        charm_state=charm_state,
        workload_config=workload_config,
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


def test_rotate_secret_key_action(harness: Harness):
    """
    arrange: none
    act: invoke the rotate-secret-key callback function
    assert: the action should change the secret key value in the relation data and restart the
        flask application with the new secret key.
    """
    container = harness.model.unit.get_container(FLASK_CONTAINER_NAME)
    container.add_layer("a_layer", DEFAULT_LAYER)
    harness.begin_with_initial_hooks()
    action_event = unittest.mock.MagicMock()
    secret_key = harness.get_relation_data(0, harness.charm.app)["flask_secret_key"]
    assert secret_key
    harness.charm._on_rotate_secret_key_action(action_event)
    new_secret_key = harness.get_relation_data(0, harness.charm.app)["flask_secret_key"]
    assert secret_key != new_secret_key


def test_integrations_wiring(harness: Harness):
    """
    arrange: Prepare a Redis a database and a S3 integration
    act: Start the flask charm and set flask-app container to be ready.
    assert: The flask service should have environment variables in its plan
        for each of the integrations.
    """
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
    s3_relation_data = {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
        "bucket": "flask-bucket",
    }
    harness.add_relation("s3", "s3-integration", app_data=s3_relation_data)
    harness.add_relation("saml", "saml-integrator", app_data=SAML_APP_RELATION_DATA_EXAMPLE)

    harness.set_leader(True)
    container = harness.model.unit.get_container(FLASK_CONTAINER_NAME)
    container.add_layer("a_layer", DEFAULT_LAYER)

    harness.begin_with_initial_hooks()
    assert harness.model.unit.status == ops.ActiveStatus()
    service_env = container.get_plan().services["flask"].environment
    assert "MYSQL_DB_CONNECT_STRING" not in service_env
    assert service_env["REDIS_DB_CONNECT_STRING"] == "redis://10.1.88.132:6379"
    assert (
        service_env["POSTGRESQL_DB_CONNECT_STRING"]
        == "postgresql://test-username:test-password@test-postgresql:5432/test-database"
    )
    assert service_env["SAML_ENTITY_ID"] == SAML_APP_RELATION_DATA_EXAMPLE["entity_id"]


def test_invalid_config(harness: Harness):
    """
    arrange: Prepare the harness. Instantiate the charm.
    act: update the config to an invalid env variables (must be more than 1 chars).
    assert: The flask service is blocked with invalid configuration.
    """
    harness.begin()
    harness.update_config({"flask-env": ""})
    assert harness.model.unit.status == ops.BlockedStatus("invalid configuration: flask-env")


def test_invalid_integration(harness: Harness):
    """
    arrange: Prepare the harness. Instantiate the charm.
    act: Integrate with an invalid integration.
    assert: The flask service is blocked because the integration data is wrong.
    """
    s3_relation_data = {
        # Missing required access-key and secret-key.
        "bucket": "flask-bucket",
    }
    harness.add_relation("s3", "s3-integration", app_data=s3_relation_data)
    harness.begin_with_initial_hooks()
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "S3" in str(harness.model.unit.status.message)
