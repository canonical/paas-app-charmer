# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Generic class to represent applications without specific requirements."""

from paas_app_charmer.app import App

class GenericApp(App):  # pylint: disable=too-few-public-methods
    """Generic application manager."""

    def gen_environment(self) -> dict[str, str]:
        """Generate a environment dictionary from the charm configurations.

        Returns:
            A dictionary representing the application environment variables.
        """
        return self._gen_environment(config_prefix="APP_", integrations_prefix="APP_")

    # JAVI look what is generic and what is not.
    def restart(self) -> None:
        """Restart or start the service if not started with the latest configuration."""
        # JAVI basically a copy paste from WsgiApp, except:
        #   the webserver part.
        #   the migration scripts that use python
        self._container.add_layer("charm", self._app_layer(), combine=True)
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
