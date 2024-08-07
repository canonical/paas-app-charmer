# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the WsgiApp class to represent the WSGI application."""

import json
import logging

import ops

from paas_app_charmer._gunicorn.webserver import GunicornWebserver
from paas_app_charmer.app import App, WorkloadConfig
from paas_app_charmer.charm_state import CharmState
from paas_app_charmer.database_migration import DatabaseMigration

logger = logging.getLogger(__name__)


class WsgiApp(App):
    """WSGI application manager."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        container: ops.Container,
        charm_state: CharmState,
        workload_config: WorkloadConfig,
        database_migration: DatabaseMigration,
        webserver: GunicornWebserver,
    ):
        """Construct the WsgiApp instance.

        Args:
            container: The WSGI application container.
            charm_state: The state of the charm.
            workload_config: The state of the workload that the WsgiApp belongs to.
            database_migration: The database migration manager object.
            webserver: The webserver manager object.
        """
        super().__init__(
            container=container,
            charm_state=charm_state,
            workload_config=workload_config,
            database_migration=database_migration,
        )
        self._webserver = webserver

    def gen_environment(self) -> dict[str, str]:
        """Generate a WSGI environment dictionary from the charm WSGI configurations.

        Returns:
            A dictionary representing the WSGI application environment variables.
        """
        prefix = f"{self._workload_config.framework.upper()}_"
        return self._gen_environment(config_prefix=prefix)

    def restart(self) -> None:
        """Restart or start the WSGI service if not started with the latest configuration."""
        self._container.add_layer("charm", self._app_layer(), combine=True)
        service_name = self._workload_config.service_name
        is_webserver_running = self._container.get_service(service_name).is_running()
        command = self._app_layer()["services"][self._workload_config.framework]["command"]
        self._webserver.update_config(
            environment=self.gen_environment(),
            is_webserver_running=is_webserver_running,
            command=command,
        )
        migration_command = None
        app_dir = self._workload_config.app_dir
        if self._container.exists(app_dir / "migrate"):
            migration_command = [str((app_dir / "migrate").absolute())]
        if self._container.exists(app_dir / "migrate.sh"):
            migration_command = ["bash", "-eo", "pipefail", "migrate.sh"]
        if self._container.exists(app_dir / "migrate.py"):
            migration_command = ["python3", "migrate.py"]
        if self._container.exists(app_dir / "manage.py"):
            # Django migrate command
            migration_command = ["python3", "manage.py", "migrate"]
        if migration_command:
            self._database_migration.run(
                command=migration_command,
                environment=self.gen_environment(),
                working_dir=app_dir,
                user=self._workload_config.user,
                group=self._workload_config.group,
            )
        self._container.replan()
