# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the WsgiApp class to represent the WSGI application."""

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
            configuration_prefix=f"{workload_config.framework.upper()}_",
            framework_config_prefix=f"{workload_config.framework.upper()}_",
            integrations_prefix="",
        )
        self._webserver = webserver

    def _prepare_service_for_restart(self) -> None:
        """Specific framework operations before restarting the service."""
        service_name = self._workload_config.service_name
        is_webserver_running = self._container.get_service(service_name).is_running()
        command = self._app_layer()["services"][self._workload_config.framework]["command"]
        self._webserver.update_config(
            environment=self.gen_environment(),
            is_webserver_running=is_webserver_running,
            command=command,
        )
