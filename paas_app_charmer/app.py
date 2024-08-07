# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the base class to represent the application."""

import abc
import json
import logging
import pathlib
import urllib.parse
from dataclasses import dataclass
from typing import List

from paas_app_charmer.charm_state import IntegrationsState

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class WorkloadConfig:  # pylint: disable=too-many-instance-attributes
    """Base Configuration for App.

    This class contains attributes that are configuration for the app/workload.

    Attrs:
        framework: the framework name.
        container_name: The container name.
        port: the port number to use for the server.
        user: The UNIX user name for running the service.
        group: The UNIX group name for running the service.
        base_dir: The project base directory in the application container.
        app_dir: The application directory in the application container.
        state_dir: the directory in the application container to store states information.
        service_name: The WSGI application pebble service name.
        log_files: List of files to monitor.
        metrics_target: Target to scrape for metrics.
        metrics_path: Path to scrape for metrics.
    """

    framework: str
    container_name: str
    port: int
    user: str = "_daemon_"
    group: str = "_daemon_"
    base_dir: pathlib.Path
    app_dir: pathlib.Path
    state_dir: pathlib.Path
    service_name: str
    log_files: List[pathlib.Path]
    metrics_target: str | None = None
    metrics_path: str | None = "/metrics"


class App(abc.ABC):
    """Base class for the application manager."""

    @abc.abstractmethod
    def gen_environment(self) -> dict[str, str]:
        """Generate a environment dictionary from the charm configurations."""

    @abc.abstractmethod
    def stop_all_services(self) -> None:
        """Stop all the services in the workload."""

    @abc.abstractmethod
    def restart(self) -> None:
        """Restart or start the WSGI service if not started with the latest configuration."""


def map_integrations_to_env(integrations: IntegrationsState, prefix: str = "") -> dict[str, str]:
    """Generate environment variables for the IntegrationState.

    Args:
       integrations: The IntegrationsState information.
       prefix: Prefix to append to the env variables.

    Returns:
       A dictionary representing the environment variables for the IntegrationState.
    """
    env = {}
    if integrations.redis_uri:
        redis_envvars = _db_url_to_env_variables("redis", integrations.redis_uri)
        env.update(redis_envvars)
    for interface_name, uri in integrations.databases_uris.items():
        interface_envvars = _db_url_to_env_variables(interface_name, uri)
        env.update(interface_envvars)

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

    return {prefix + k: v for k, v in env.items()}


def _db_url_to_env_variables(base_name: str, url: str) -> dict[str, str]:
    """Convert a database url to environment variables.

    Args:
      base_name: name of the database.
      url: url of the database

    Return:
      All environment variables, that is, the connection string,
      all components as returned from urllib.parse and the
      database name extracted from the path
    """
    if not url:
        return {}

    base_name = base_name.upper()
    envvars: dict[str, str | None] = {}
    envvars[f"{base_name}_DB_CONNECT_STRING"] = url

    parsed_url = urllib.parse.urlparse(url)

    # All components of urlparse, using the same convention for default values.
    # See: https://docs.python.org/3/library/urllib.parse.html#url-parsing
    envvars[f"{base_name}_DB_SCHEME"] = parsed_url.scheme
    envvars[f"{base_name}_DB_NETLOC"] = parsed_url.netloc
    envvars[f"{base_name}_DB_PATH"] = parsed_url.path
    envvars[f"{base_name}_DB_PARAMS"] = parsed_url.params
    envvars[f"{base_name}_DB_QUERY"] = parsed_url.query
    envvars[f"{base_name}_DB_FRAGMENT"] = parsed_url.fragment
    envvars[f"{base_name}_DB_USERNAME"] = parsed_url.username
    envvars[f"{base_name}_DB_PASSWORD"] = parsed_url.password
    envvars[f"{base_name}_DB_HOSTNAME"] = parsed_url.hostname
    envvars[f"{base_name}_DB_PORT"] = str(parsed_url.port) if parsed_url.port is not None else None

    # database name is usually parsed this way.
    envvars[f"{base_name}_DB_NAME"] = (
        parsed_url.path.removeprefix("/") if parsed_url.path else None
    )

    return {k: v for k, v in envvars.items() if v is not None}
