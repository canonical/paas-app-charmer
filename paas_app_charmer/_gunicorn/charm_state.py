# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""This module defines the CharmState class which represents the state of the charm."""
import os
import pathlib
import typing

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires

# pydantic is causing this no-name-in-module problem
from pydantic import BaseModel, Field  # pylint: disable=no-name-in-module

from paas_app_charmer._gunicorn.secret_storage import GunicornSecretStorage
from paas_app_charmer._gunicorn.webserver import WebserverConfig
from paas_app_charmer.databases import get_uris


class ProxyConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Configuration for network access through proxy.

    Attributes:
        http_proxy: The http proxy URL.
        https_proxy: The https proxy URL.
        no_proxy: Comma separated list of hostnames to bypass proxy.
    """

    http_proxy: str | None = Field(default=None, pattern="https?://.+")
    https_proxy: str | None = Field(default=None, pattern="https?://.+")
    no_proxy: typing.Optional[str] = None


# too-many-instance-attributes is okay since we use a factory function to construct the CharmState
class CharmState:  # pylint: disable=too-many-instance-attributes
    """Represents the state of the Gunicorn based charm.

    Attrs:
        webserver_config: the web server configuration file content for the charm.
        wsgi_config: the value of the WSGI specific charm configuration.
        app_config: user-defined configurations for the WSGI application.
        database_uris: a mapping of available database environment variable to database uris.
        port: the port number to use for the WSGI server.
        application_log_file: the file path for the WSGI application access log.
        application_error_log_file: the file path for the WSGI application error log.
        statsd_host: the statsd server host for WSGI application metrics.
        secret_key: the charm managed WSGI application secret key.
        is_secret_storage_ready: whether the secret storage system is ready.
        proxy: proxy information.
        service_name: The WSGI application pebble service name.
        container_name: The name of the WSGI application container.
        base_dir: The project base directory in the WSGI application container.
        app_dir: The WSGI application directory in the WSGI application container.
        user: The UNIX user name for running the service.
        group: The UNIX group name for running the service
    """

    statsd_host = "localhost:9125"
    port = 8000
    user = "_daemon_"
    group = "_daemon_"

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        framework: str,
        webserver_config: WebserverConfig,
        is_secret_storage_ready: bool,
        app_config: dict[str, int | str | bool] | None = None,
        database_requirers: dict[str, DatabaseRequires] | None = None,
        wsgi_config: dict[str, int | str] | None = None,
        secret_key: str | None = None,
    ):
        """Initialize a new instance of the CharmState class.

        Args:
            framework: the framework name.
            webserver_config: the Gunicorn webserver configuration.
            is_secret_storage_ready: whether the secret storage system is ready.
            app_config: User-defined configuration values for the WSGI application configuration.
            wsgi_config: The value of the WSGI application specific charm configuration.
            secret_key: The secret storage manager associated with the charm.
            database_requirers: All declared database requirers.
        """
        self.framework = framework
        self.service_name = self.framework
        self.container_name = f"{self.framework}-app"
        self.base_dir = pathlib.Path(f"/{framework}")
        self.app_dir = self.base_dir / "app"
        self.state_dir = self.base_dir / "state"
        self.application_log_file = pathlib.Path(f"/var/log/{self.framework}/access.log")
        self.application_error_log_file = pathlib.Path(f"/var/log/{self.framework}/error.log")
        self.webserver_config = webserver_config
        self._wsgi_config = wsgi_config if wsgi_config is not None else {}
        self._app_config = app_config if app_config is not None else {}
        self._is_secret_storage_ready = is_secret_storage_ready
        self._secret_key = secret_key
        self._database_requirers = database_requirers if database_requirers else {}

    @classmethod
    def from_charm(  # pylint: disable=too-many-arguments
        cls,
        charm: ops.CharmBase,
        framework: str,
        wsgi_config: BaseModel,
        secret_storage: GunicornSecretStorage,
        database_requirers: dict[str, DatabaseRequires],
    ) -> "CharmState":
        """Initialize a new instance of the CharmState class from the associated charm.

        Args:
            charm: The charm instance associated with this state.
            framework: The WSGI framework name.
            wsgi_config: The WSGI framework specific configurations.
            secret_storage: The secret storage manager associated with the charm.
            database_requirers: All database requirers object declared by the charm.

        Return:
            The CharmState instance created by the provided charm.
        """
        app_config = {
            k.replace("-", "_"): v
            for k, v in charm.config.items()
            if not any(k.startswith(prefix) for prefix in (f"{framework}-", "webserver-"))
        }
        app_config = {k: v for k, v in app_config.items() if k not in wsgi_config.dict().keys()}
        return cls(
            framework=framework,
            wsgi_config=wsgi_config.dict(exclude_unset=True, exclude_none=True),
            app_config=typing.cast(dict[str, str | int | bool], app_config),
            database_requirers=database_requirers,
            webserver_config=WebserverConfig.from_charm(charm),
            secret_key=(
                secret_storage.get_secret_key() if secret_storage.is_initialized else None
            ),
            is_secret_storage_ready=secret_storage.is_initialized,
        )

    @property
    def proxy(self) -> "ProxyConfig":
        """Get charm proxy information from juju charm environment.

        Returns:
            charm proxy information in the form of `ProxyConfig`.
        """
        http_proxy = os.environ.get("JUJU_CHARM_HTTP_PROXY")
        https_proxy = os.environ.get("JUJU_CHARM_HTTPS_PROXY")
        no_proxy = os.environ.get("JUJU_CHARM_NO_PROXY")
        return ProxyConfig(
            http_proxy=http_proxy if http_proxy else None,
            https_proxy=https_proxy if https_proxy else None,
            no_proxy=no_proxy,
        )

    @property
    def wsgi_config(self) -> dict[str, str | int | bool]:
        """Get the value of the WSGI application specific configuration.

        Returns:
            The value of the WSGI application specific configuration.
        """
        return self._wsgi_config

    @property
    def app_config(self) -> dict[str, str | int | bool]:
        """Get the value of user-defined application configurations.

        Returns:
            The value of user-defined application configurations.
        """
        return self._app_config

    @property
    def secret_key(self) -> str:
        """Return the WSGI application secret key stored in the SecretStorage.

        It's an error to read the secret key before SecretStorage is initialized.

        Returns:
            The WSGI application secret key stored in the SecretStorage.

        Raises:
            RuntimeError: raised when accessing WSGI application secret key before
                          secret storage is ready.
        """
        if self._secret_key is None:
            raise RuntimeError("access secret key before secret storage is ready")
        return self._secret_key

    @property
    def is_secret_storage_ready(self) -> bool:
        """Return whether the secret storage system is ready.

        Returns:
            Whether the secret storage system is ready.
        """
        return self._is_secret_storage_ready

    @property
    def database_uris(self) -> dict[str, str]:
        """Return currently attached database URIs.

        Returns:
            A dictionary of database types and database URIs.
        """
        return get_uris(self._database_requirers)
