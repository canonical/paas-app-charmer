# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""This module defines the CharmState class which represents the state of the charm."""
import os
import typing
from dataclasses import dataclass, field

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires

# pydantic is causing this no-name-in-module problem
from pydantic import BaseModel, Field  # pylint: disable=no-name-in-module

from paas_app_charmer._gunicorn.secret_storage import GunicornSecretStorage
from paas_app_charmer.databases import get_uri


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
        wsgi_config: the value of the WSGI specific charm configuration.
        app_config: user-defined configurations for the WSGI application.
        port: the port number to use for the WSGI server.
        statsd_host: the statsd server host for WSGI application metrics.
        secret_key: the charm managed WSGI application secret key.
        is_secret_storage_ready: whether the secret storage system is ready.
        proxy: proxy information.
        service_name: The WSGI application pebble service name.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        framework: str,
        is_secret_storage_ready: bool,
        app_config: dict[str, int | str | bool] | None = None,
        wsgi_config: dict[str, int | str] | None = None,
        secret_key: str | None = None,
        integrations: "IntegrationsState | None" = None,
    ):
        """Initialize a new instance of the CharmState class.

        Args:
            framework: the framework name.
            is_secret_storage_ready: whether the secret storage system is ready.
            app_config: User-defined configuration values for the WSGI application configuration.
            wsgi_config: The value of the WSGI application specific charm configuration.
            secret_key: The secret storage manager associated with the charm.
            integrations: Information about the integrations.
        """
        self.framework = framework
        self._wsgi_config = wsgi_config if wsgi_config is not None else {}
        self._app_config = app_config if app_config is not None else {}
        self._is_secret_storage_ready = is_secret_storage_ready
        self._secret_key = secret_key
        self.integrations = integrations

    @classmethod
    def from_charm(  # pylint: disable=too-many-arguments
        cls,
        charm: ops.CharmBase,
        framework: str,
        wsgi_config: BaseModel,
        secret_storage: GunicornSecretStorage,
        database_requirers: dict[str, DatabaseRequires],
        redis_uri: str | None = None,
    ) -> "CharmState":
        """Initialize a new instance of the CharmState class from the associated charm.

        Args:
            charm: The charm instance associated with this state.
            framework: The WSGI framework name.
            wsgi_config: The WSGI framework specific configurations.
            secret_storage: The secret storage manager associated with the charm.
            database_requirers: All database requirers object declared by the charm.
            redis_uri: The redis uri provided by the redis charm.

        Return:
            The CharmState instance created by the provided charm.
        """
        app_config = {
            k.replace("-", "_"): v
            for k, v in charm.config.items()
            if not any(k.startswith(prefix) for prefix in (f"{framework}-", "webserver-"))
        }
        app_config = {k: v for k, v in app_config.items() if k not in wsgi_config.dict().keys()}

        integrations = IntegrationsState.build(
            redis_uri=redis_uri,
            database_requirers=database_requirers,
        )
        return cls(
            framework=framework,
            wsgi_config=wsgi_config.dict(exclude_unset=True, exclude_none=True),
            app_config=typing.cast(dict[str, str | int | bool], app_config),
            secret_key=(
                secret_storage.get_secret_key() if secret_storage.is_initialized else None
            ),
            is_secret_storage_ready=secret_storage.is_initialized,
            integrations=integrations,
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


@dataclass
class IntegrationsState:
    """State of the integrations.

    This state is related to all the relations that can be optional, like databases, redis...

    Attrs:
        redis_uri: The redis uri provided by the redis charm.
        databases_uris: Map from interface_name to the database uri.
    """

    redis_uri: str | None = None
    databases_uris: dict[str, str | None] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        redis_uri: str | None,
        database_requirers: dict[str, DatabaseRequires],
    ) -> "IntegrationsState":
        """Initialize a new instance of the IntegrationsState class.

        Args:
            redis_uri: The redis uri provided by the redis charm.
            database_requirers: All database requirers object declared by the charm.

        Return:
            The IntegrationsState instance created.
        """
        return cls(
            redis_uri=redis_uri,
            databases_uris={
                interface_name: get_uri(uri) for interface_name, uri in database_requirers.items()
            },
        )
