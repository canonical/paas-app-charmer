# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""This module defines the CharmState class which represents the state of the charm."""
import logging
import os
import pathlib
import typing

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires

# pydantic is causing this no-name-in-module problem
from pydantic import BaseModel, Field, ValidationError  # pylint: disable=no-name-in-module

from paas_app_charmer._gunicorn.secret_storage import GunicornSecretStorage
from paas_app_charmer._gunicorn.webserver import WebserverConfig
from paas_app_charmer.databases import get_uris

logger = logger = logging.getLogger(__name__)


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
        group: The UNIX group name for running the service.
        redis_uri: The redis uri provided by the redis charm.
        s3_parameters: S3 parameters.
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
        redis_uri: str | None = None,
        s3_connection_info: dict[str, str] | None = None,
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
            redis_uri: The redis uri provided by the redis charm.
            s3_connection_info: S3 connection info provided by the s3-integrator charm.
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
        self.redis_uri = redis_uri
        self._wsgi_config = wsgi_config if wsgi_config is not None else {}
        self._app_config = app_config if app_config is not None else {}
        self._is_secret_storage_ready = is_secret_storage_ready
        self._secret_key = secret_key
        self._database_requirers = database_requirers if database_requirers else {}
        self._s3_connection_info = s3_connection_info

    @classmethod
    def from_charm(  # pylint: disable=too-many-arguments
        cls,
        charm: ops.CharmBase,
        framework: str,
        wsgi_config: BaseModel,
        secret_storage: GunicornSecretStorage,
        database_requirers: dict[str, DatabaseRequires],
        redis_uri: str | None = None,
        s3_connection_info: dict[str, str] | None = None,
    ) -> "CharmState":
        """Initialize a new instance of the CharmState class from the associated charm.

        Args:
            charm: The charm instance associated with this state.
            framework: The WSGI framework name.
            wsgi_config: The WSGI framework specific configurations.
            secret_storage: The secret storage manager associated with the charm.
            database_requirers: All database requirers object declared by the charm.
            redis_uri: The redis uri provided by the redis charm.
            s3_connection_info: The S3 connection info.

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
            redis_uri=redis_uri,
            s3_connection_info=s3_connection_info,
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

    @property
    def s3_parameters(self) -> typing.Optional["S3Parameters"]:
        """Returns S3Parameters or None if they do not exist or are invalid.

        Returns:
            S3Parameters or None.
        """
        if not self._s3_connection_info:
            return None

        try:
            s3_parameters = S3Parameters(**self._s3_connection_info)
        except ValidationError:
            logger.exception("Invalid/Missing S3 parameters.")
            return None
        return s3_parameters


class S3Parameters(BaseModel):  # pylint: disable=no-member
    """Configuration for accessing S3 bucket.

    Attributes:
        access_key: AWS access key.
        secret_key: AWS secret key.
        region: The region to connect to the object storage.
        storage_class: Storage Class for objects uploaded to the object storage.
        bucket: The bucket name.
        endpoint: The endpoint used to connect to the object storage.
        path: The path inside the bucket to store objects.
        s3_api_version: S3 protocol specific API signature.
        s3_uri_style: The S3 protocol specific bucket path lookup type. Can be "path" or "host".
        tls_ca_chain: The complete CA chain, which can be used for HTTPS validation.
        addressing_style: S3 protocol addressing style, can be "path" or "virtual".
        attributes: The custom metadata (HTTP headers).
    """

    access_key: str = Field(alias="access-key")
    secret_key: str = Field(alias="secret-key")
    region: typing.Optional[str] = None
    storage_class: typing.Optional[str] = Field(alias="storage-class", default=None)
    bucket: str
    endpoint: typing.Optional[str] = None
    path: typing.Optional[str] = None
    s3_api_version: typing.Optional[str] = Field(alias="s3-api-version", default=None)
    s3_uri_style: typing.Optional[str] = Field(alias="s3-uri-style", default=None)
    tls_ca_chain: typing.Optional[str] = Field(alias="tls-ca-chain", default=None)
    attributes: typing.Optional[str] = None

    @property
    def addressing_style(self) -> typing.Optional[str]:
        """Translates s3_uri_style to AWS addressing_style."""
        if self.s3_uri_style == "host":
            return "virtual"
        # If None or "path", it does not change.
        return self.s3_uri_style

    def to_env(self) -> dict[str, str]:
        """Convert to env variables.

        Returns:
           dict with environment variables for django storage.
        """
        # For S3 fields reference see:
        # https://github.com/canonical/charm-relation-interfaces/tree/main/interfaces/s3/v0
        storage_dict = {
            "S3_ACCESS_KEY": self.access_key,
            "S3_SECRET_KEY": self.secret_key,  # or S3_SECRET_KEY?
            "S3_REGION": self.region,
            "S3_STORAGE_CLASS": self.storage_class,
            "S3_BUCKET": self.bucket,
            "S3_ENDPOINT": self.endpoint,
            "S3_PATH": self.path,
            "S3_API_VERSION": self.s3_api_version,
            "S3_URI_STYLE": self.s3_uri_style,
            "S3_TLS_CA_CHAIN": self.tls_ca_chain,
            "S3_ADDRESSING_STYLE": self.addressing_style,
        }
        return {k: v for k, v in storage_dict.items() if v is not None}
