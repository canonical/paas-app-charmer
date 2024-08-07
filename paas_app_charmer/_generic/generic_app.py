# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Generic class to represent applications without specific requirements."""

import json
import logging

import ops

from paas_app_charmer.app import App, WorkloadConfig, encode_env, map_integrations_to_env
from paas_app_charmer.charm_state import CharmState
from paas_app_charmer.database_migration import DatabaseMigration

logger = logging.getLogger(__name__)


class GenericApp(App):  # pylint: disable=too-few-public-methods
    """Generic application manager."""

    def __init__(
        self,
        container: ops.Container,
        charm_state: CharmState,
        workload_config: WorkloadConfig,
        database_migration: DatabaseMigration,
    ):
        """Construct the instance.

        Args:
            container: The application container.
            charm_state: The state of the charm.
            workload_config: The state of the workload that the App belongs to.
            database_migration: The database migration manager object.
        """
        self._charm_state = charm_state
        self._workload_config = workload_config
        self._container = container
        self._database_migration = database_migration

    # JAVI look what is generic and what is not.
    # Basically copy pasted...
    def gen_environment(self) -> dict[str, str]:
        """Generate a environment dictionary from the charm configurations.

        Returns:
            A dictionary representing the application environment variables.
        """
        # JAVI remove this line
        # pylint: disable=R0801
        config = self._charm_state.app_config
        config.update(self._charm_state.framework_config)
        prefix = "APP_"
        env = {f"{prefix}{k.upper()}": encode_env(v) for k, v in config.items()}
        if self._charm_state.base_url:
            env[f"{prefix}BASE_URL"] = self._charm_state.base_url
        secret_key_env = f"{prefix}SECRET_KEY"
        if secret_key_env not in env:
            env[secret_key_env] = self._charm_state.secret_key
        for proxy_variable in ("http_proxy", "https_proxy", "no_proxy"):
            proxy_value = getattr(self._charm_state.proxy, proxy_variable)
            if proxy_value:
                env[proxy_variable] = str(proxy_value)
                env[proxy_variable.upper()] = str(proxy_value)

        if self._charm_state.integrations:
            env.update(map_integrations_to_env(self._charm_state.integrations, prefix=prefix))
        return env

    # JAVI copy pasted from WsgiAPP. Extract somewhere.
    def _wsgi_layer(self) -> ops.pebble.LayerDict:
        """Generate the pebble layer definition for the application.

        Returns:
            The pebble layer definition for the application.
        """
        # JAVI remove this line
        # pylint: disable=R0801
        original_services_file = self._workload_config.state_dir / "original-services.json"
        if self._container.exists(original_services_file):
            services = json.loads(self._container.pull(original_services_file).read())
        else:
            plan = self._container.get_plan()
            services = {k: v.to_dict() for k, v in plan.services.items()}
            self._container.push(original_services_file, json.dumps(services), make_dirs=True)

        services[self._workload_config.service_name]["override"] = "replace"
        services[self._workload_config.service_name]["environment"] = self.gen_environment()

        return ops.pebble.LayerDict(services=services)

    # JAVI look what is generic and what is not.
    def restart(self) -> None:
        """Restart or start the service if not started with the latest configuration."""
        # JAVI basically a copy paste from WsgiApp, except:
        #   the webserver part.
        #   the migration scripts that use python
        self._container.add_layer("charm", self._wsgi_layer(), combine=True)
        migration_command = None
        app_dir = self._workload_config.app_dir
        if self._container.exists(app_dir / "migrate"):
            migration_command = [str((app_dir / "migrate").absolute())]
        if self._container.exists(app_dir / "migrate.sh"):
            migration_command = ["bash", "-eo", "pipefail", "migrate.sh"]
        if migration_command:
            self._database_migration.run(
                command=migration_command,
                environment=self.gen_environment(),
                working_dir=app_dir,
                user=self._workload_config.user,
                group=self._workload_config.group,
            )
        self._container.replan()

    # JAVI put this in the base class?
    def stop_all_services(self) -> None:
        """Stop all the services in the workload.

        Services will restarted again when the restart method is invoked.
        """
        services = self._container.get_services()
        service_names = list(services.keys())
        if service_names:
            self._container.stop(*service_names)
