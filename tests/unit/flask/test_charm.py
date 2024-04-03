# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Flask charm unit tests."""
import datetime
import os
import unittest.mock

from ops.testing import Harness

from paas_app_charmer._gunicorn import logrotate
from paas_app_charmer._gunicorn.charm_state import CharmState
from paas_app_charmer._gunicorn.webserver import GunicornWebserver
from paas_app_charmer._gunicorn.wsgi_app import WsgiApp
from paas_app_charmer.flask import Charm

from .constants import DEFAULT_LAYER, FLASK_CONTAINER_NAME

# this is a unit test file
# pylint: disable=protected-access


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


def test_log_rotate(tmp_path):
    """
    arrange: create a log file larger than the max log file size
    act: run the log rotate function
    assert: the log file has rotated
    """
    log_file = tmp_path / "access.log"
    log_file.touch()
    os.truncate(log_file, logrotate.MAX_SIZE + 1)
    assert logrotate.rotate(str(log_file.absolute()))
    assert not log_file.exists()
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    archive = files[0]
    datetime.datetime.strptime(archive.name, "access-%Y-%m-%d-%H-%M-%S.log")


def test_log_rotate_cleanup(tmp_path):
    """
    arrange: create a log file larger than the max log file size, along with many archive files
    act: run the log rotate function
    assert: the log file has rotated and old archive files were removed
    """
    log_file = tmp_path / "access.log"
    log_file.touch()
    os.truncate(log_file, logrotate.MAX_SIZE + 1)
    for i in range(10):
        (tmp_path / f"access-0001-01-01-01-01-{i:0>2}.log").touch()
    assert logrotate.rotate(str(log_file.absolute()))
    assert not log_file.exists()
    files = list(tmp_path.iterdir())
    assert len(files) == logrotate.KEEP_ARCHIVES
    assert (
        len([f for f in files if f.name.startswith("access-0001")]) == logrotate.KEEP_ARCHIVES - 1
    )
