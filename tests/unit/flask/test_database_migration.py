# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for Flask charm database integration."""
import pathlib

import ops
import pytest
from ops.testing import Harness

from paas_app_charmer._gunicorn.charm_state import CharmState
from paas_app_charmer._gunicorn.webserver import GunicornWebserver, WebserverConfig
from paas_app_charmer._gunicorn.wsgi_app import WsgiApp
from paas_app_charmer.database_migration import DatabaseMigration, DatabaseMigrationStatus
from paas_app_charmer.exceptions import CharmConfigInvalidError

from .constants import DEFAULT_LAYER, FLASK_CONTAINER_NAME


def test_database_migration(harness: Harness):
    """
    arrange: none
    act: set the database migration script to be different value.
    assert: the restart_flask method will not invoke the database migration script after the
        first successful run.
    """
    harness.begin()
    container: ops.Container = harness.model.unit.get_container(FLASK_CONTAINER_NAME)
    container.add_layer("default", DEFAULT_LAYER)
    root = harness.get_filesystem_root(container)
    harness.set_can_connect(container, True)
    charm_state = CharmState(
        framework="flask",
        webserver_config=WebserverConfig(),
        is_secret_storage_ready=True,
        secret_key="",
    )
    webserver = GunicornWebserver(
        charm_state=charm_state,
        container=container,
    )
    database_migration = DatabaseMigration(
        container=container, state_dir=pathlib.Path("/flask/state")
    )
    flask_app = WsgiApp(
        container=container,
        charm_state=charm_state,
        webserver=webserver,
        database_migration=database_migration,
    )
    database_migration_history = []
    migration_return_code = 0

    def handle_database_migration(args: ops.testing.ExecArgs):
        """Handle the database migration command."""
        database_migration_history.append(args.command)
        return ops.testing.ExecResult(migration_return_code)

    harness.handle_exec(container, [], handler=handle_database_migration)
    (root / "flask/app/migrate.sh").touch()

    migration_return_code = 1
    with pytest.raises(CharmConfigInvalidError):
        flask_app.restart()
    assert database_migration_history == [["bash", "-eo", "pipefail", "migrate.sh"]]

    migration_return_code = 0
    flask_app.restart()
    assert database_migration_history == [["bash", "-eo", "pipefail", "migrate.sh"]] * 2

    flask_app.restart()
    assert database_migration_history == [["bash", "-eo", "pipefail", "migrate.sh"]] * 2

    (root / "flask/app/migrate.py").touch()
    (root / "flask/app/migrate.sh").unlink()

    flask_app.restart()
    assert database_migration_history == [["bash", "-eo", "pipefail", "migrate.sh"]] * 2


@pytest.mark.parametrize(
    "file,command",
    [
        pytest.param("migrate", ["/flask/app/migrate"], id="executable"),
        pytest.param("migrate.sh", ["bash", "-eo", "pipefail", "migrate.sh"], id="shell"),
        pytest.param("migrate.py", ["python", "migrate.py"], id="python"),
    ],
)
def test_database_migrate_command(harness: Harness, file: str, command: list[str]):
    """
    arrange: set up the test harness
    act: run the database migration with different database migration scripts
    assert: database migration should run different command accordingly
    """
    harness.begin()
    container: ops.Container = harness.model.unit.get_container(FLASK_CONTAINER_NAME)
    container.add_layer("default", DEFAULT_LAYER)
    root = harness.get_filesystem_root(container)
    (root / "flask/app" / file).touch()
    harness.set_can_connect(container, True)
    charm_state = CharmState(
        framework="flask",
        webserver_config=WebserverConfig(),
        is_secret_storage_ready=True,
        secret_key="",
    )
    webserver = GunicornWebserver(
        charm_state=charm_state,
        container=container,
    )
    database_migration = DatabaseMigration(
        container=container, state_dir=pathlib.Path("/flask/state")
    )
    flask_app = WsgiApp(
        container=container,
        charm_state=charm_state,
        webserver=webserver,
        database_migration=database_migration,
    )
    history = []
    harness.handle_exec(container, [], handler=lambda args: history.append(args.command))

    flask_app.restart()

    assert len(history) == 1
    assert history[0] == command


def test_database_migration_status(harness: Harness):
    """
    arrange: set up the test harness
    act: run the database migration with migration run sets to fail or succeed
    assert: database migration instance should report correct status.
    """
    harness.begin()
    container = harness.charm.unit.get_container(FLASK_CONTAINER_NAME)
    container.add_layer("default", DEFAULT_LAYER)

    harness.handle_exec(container, [], result=1)
    database_migration = DatabaseMigration(
        container=container, state_dir=pathlib.Path("/flask/state")
    )
    assert database_migration.get_status() == DatabaseMigrationStatus.PENDING
    with pytest.raises(CharmConfigInvalidError):
        database_migration.run(["migrate"], {}, pathlib.Path("/flask/app"))
    assert database_migration.get_status() == DatabaseMigrationStatus.FAILED
    harness.handle_exec(container, [], result=0)
    database_migration.run(["migrate"], {}, pathlib.Path("/flask/app"))
    assert database_migration.get_status() == DatabaseMigrationStatus.COMPLETED
