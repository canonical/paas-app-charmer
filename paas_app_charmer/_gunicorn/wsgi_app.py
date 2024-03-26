# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the WsgiApp class to represent the WSGI application."""

import json
import logging

import ops

from paas_app_charmer._gunicorn.charm_state import CharmState
from paas_app_charmer._gunicorn.webserver import GunicornWebserver
from paas_app_charmer.database_migration import DatabaseMigration

logger = logging.getLogger(__name__)


class WsgiApp:  # pylint: disable=too-few-public-methods
    """WSGI application manager."""

    def __init__(
        self,
        container: ops.Container,
        charm_state: CharmState,
        webserver: GunicornWebserver,
        database_migration: DatabaseMigration,
    ):
        """Construct the WsgiApp instance.

        Args:
            container: The WSGI application container.
            charm_state: The state of the charm.
            webserver: The webserver manager object.
            database_migration: The database migration manager object.
        """
        self._charm_state = charm_state
        self._container = container
        self._webserver = webserver
        self._database_migration = database_migration

    def _encode_env(self, value: str | int | float | bool | list | dict) -> str:
        """Encode the environment variable values.

        Args:
            value: The input environment variable value.

        Return:
            The original string if the input is a string, or JSON encoded value.
        """
        return value if isinstance(value, str) else json.dumps(value)

    def gen_environment(self) -> dict[str, str]:
        """Generate a WSGI environment dictionary from the charm WSGI configurations.

        The WSGI environment generation follows these rules:
            1. User-defined configuration cannot overwrite built-in WSGI configurations, even if
                the built-in WSGI application configuration value is None (undefined).
            2. Boolean and integer-typed configuration values will be JSON encoded before
                being passed to application.
            3. String-typed configuration values will be passed to the application as environment
                variables directly.

        Returns:
            A dictionary representing the WSGI application environment variables.
        """
        config = self._charm_state.app_config
        config.update(self._charm_state.wsgi_config)
        prefix = f"{self._charm_state.framework.upper()}_"
        env = {f"{prefix}{k.upper()}": self._encode_env(v) for k, v in config.items()}
        secret_key_env = f"{prefix}SECRET_KEY"
        if secret_key_env not in env:
            env[secret_key_env] = self._charm_state.secret_key
        for proxy_variable in ("http_proxy", "https_proxy", "no_proxy"):
            proxy_value = getattr(self._charm_state.proxy, proxy_variable)
            if proxy_value:
                env[proxy_variable] = str(proxy_value)
                env[proxy_variable.upper()] = str(proxy_value)
        env.update(self._charm_state.database_uris)
        return env

    def _wsgi_layer(self) -> ops.pebble.LayerDict:
        """Generate the pebble layer definition for WSGI application.

        Returns:
            The pebble layer definition for WSGI application.
        """
        original_services_file = self._charm_state.state_dir / "original-services.json"
        if self._container.exists(original_services_file):
            services = json.loads(self._container.pull(original_services_file).read())
        else:
            plan = self._container.get_plan()
            services = {k: v.to_dict() for k, v in plan.services.items()}
            self._container.push(original_services_file, json.dumps(services), make_dirs=True)

        services[self._charm_state.service_name]["override"] = "replace"
        services[self._charm_state.service_name]["environment"] = self.gen_environment()

        return ops.pebble.LayerDict(services=services)

    def restart(self) -> None:
        """Restart or start the WSGI service if not started with the latest configuration."""
        self._container.add_layer("charm", self._wsgi_layer(), combine=True)
        service_name = self._charm_state.service_name
        is_webserver_running = self._container.get_service(service_name).is_running()
        command = self._wsgi_layer()["services"][self._charm_state.framework]["command"]
        self._webserver.update_config(
            environment=self.gen_environment(),
            is_webserver_running=is_webserver_running,
            command=command,
        )
        migration_command = None
        app_dir = self._charm_state.app_dir
        if self._container.exists(app_dir / "migrate"):
            migration_command = [str((app_dir / "migrate").absolute())]
        if self._container.exists(app_dir / "migrate.sh"):
            migration_command = ["bash", "-eo", "pipefail", "migrate.sh"]
        if self._container.exists(app_dir / "migrate.py"):
            migration_command = ["python", "migrate.py"]
        if migration_command:
            self._database_migration.run(
                command=migration_command,
                environment=self.gen_environment(),
                working_dir=app_dir,
                user=self._charm_state.user,
                group=self._charm_state.group,
            )
        self._container.replan()
