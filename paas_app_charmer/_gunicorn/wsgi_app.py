# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the WsgiApp class to represent the WSGI application."""

import json
import logging

import ops

from paas_app_charmer._gunicorn.charm_state import CharmState, IntegrationsState
from paas_app_charmer._gunicorn.webserver import GunicornWebserver
from paas_app_charmer._gunicorn.workload_config import WorkloadConfig
from paas_app_charmer.database_migration import DatabaseMigration

logger = logging.getLogger(__name__)


class WsgiApp:  # pylint: disable=too-few-public-methods
    """WSGI application manager."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        container: ops.Container,
        charm_state: CharmState,
        workload_config: WorkloadConfig,
        webserver: GunicornWebserver,
        database_migration: DatabaseMigration,
    ):
        """Construct the WsgiApp instance.

        Args:
            container: The WSGI application container.
            charm_state: The state of the charm.
            workload_config: The state of the workload that the WsgiApp belongs to.
            webserver: The webserver manager object.
            database_migration: The database migration manager object.
        """
        self._charm_state = charm_state
        self._workload_config = workload_config
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
        prefix = f"{self._workload_config.framework.upper()}_"
        env = {f"{prefix}{k.upper()}": self._encode_env(v) for k, v in config.items()}
        secret_key_env = f"{prefix}SECRET_KEY"
        if secret_key_env not in env:
            env[secret_key_env] = self._charm_state.secret_key
        for proxy_variable in ("http_proxy", "https_proxy", "no_proxy"):
            proxy_value = getattr(self._charm_state.proxy, proxy_variable)
            if proxy_value:
                env[proxy_variable] = str(proxy_value)
                env[proxy_variable.upper()] = str(proxy_value)

        if self._charm_state.integrations:
            env.update(map_integrations_to_env(self._charm_state.integrations))
        return env

    def _wsgi_layer(self) -> ops.pebble.LayerDict:
        """Generate the pebble layer definition for WSGI application.

        Returns:
            The pebble layer definition for WSGI application.
        """
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

    def stop_all_services(self) -> None:
        """Stop all the services in the workload.

        Services will restarted again when the restart method is invoked.
        """
        services = self._container.get_services()
        service_names = list(services.keys())
        if service_names:
            self._container.stop(*service_names)

    def restart(self) -> None:
        """Restart or start the WSGI service if not started with the latest configuration."""
        self._container.add_layer("charm", self._wsgi_layer(), combine=True)
        service_name = self._workload_config.service_name
        is_webserver_running = self._container.get_service(service_name).is_running()
        command = self._wsgi_layer()["services"][self._workload_config.framework]["command"]
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


def map_integrations_to_env(integrations: IntegrationsState) -> dict[str, str]:
    """Generate environment variables for the IntegrationState.

    Args:
       integrations: The IntegrationsState information.

    Returns:
       A dictionary representing the environment variables for the IntegrationState.
    """
    env = {}
    if integrations.redis_uri:
        env["REDIS_DB_CONNECT_STRING"] = integrations.redis_uri
    for interface_name, uri in integrations.databases_uris.items():
        if uri is None:
            continue
        env_name = f"{interface_name.upper()}_DB_CONNECT_STRING"
        env[env_name] = uri

    if integrations.s3_parameters:
        s3 = integrations.s3_parameters
        env.update(
            (k, v)
            for k, v in (
                ("S3_ACCESS_KEY", s3.access_key),
                ("S3_SECRET_KEY", s3.secret_key),
                ("S3_REGION", s3.region),
                ("S3_STORAGE_CLASS", s3.storage_class),
                ("S3_BUCKET", s3.bucket),
                ("S3_ENDPOINT", s3.endpoint),
                ("S3_PATH", s3.path),
                ("S3_API_VERSION", s3.s3_api_version),
                ("S3_URI_STYLE", s3.s3_uri_style),
                ("S3_ADDRESSING_STYLE", s3.addressing_style),
                ("S3_ATTRIBUTES", json.dumps(s3.attributes) if s3.attributes else None),
                ("S3_TLS_CA_CHAIN", json.dumps(s3.tls_ca_chain) if s3.attributes else None),
            )
            if v is not None
        )

    if integrations.saml_parameters:
        saml = integrations.saml_parameters
        env.update(
            (k, v)
            for k, v in (
                ("SAML_ENTITY_ID", saml.entity_id),
                ("SAML_METADATA_URL", saml.metadata_url),
                ("SAML_SINGLE_SIGN_ON_REDIRECT_URL", saml.single_sign_on_redirect_url),
                ("SAML_SIGNING_CERTIFICATE", saml.signing_certificate),
            )
            if v is not None
        )

    return env
