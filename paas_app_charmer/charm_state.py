# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""This module defines the CharmState class which represents the state of the charm."""
import logging
import os
import typing
from typing import Optional

import ops
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from paas_app_charmer.secret_storage import KeySecretStorage

logger = logging.getLogger(__name__)


class ProxyConfig(BaseModel):
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
    """Represents the state of the charm.

    Attrs:
        framework_config: the value of the framework specific charm configuration.
        app_config: user-defined configurations for the application.
        secret_key: the charm managed application secret key.
        is_secret_storage_ready: whether the secret storage system is ready.
        proxy: proxy information.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        framework: str,
        is_secret_storage_ready: bool,
        app_config: dict[str, int | str | bool] | None = None,
        framework_config: dict[str, int | str] | None = None,
        secret_key: str | None = None,
        integrations: "IntegrationsState | None" = None,
        base_url: str | None = None,
    ):
        """Initialize a new instance of the CharmState class.

        Args:
            framework: the framework name.
            is_secret_storage_ready: whether the secret storage system is ready.
            app_config: User-defined configuration values for the application configuration.
            framework_config: The value of the framework application specific charm configuration.
            secret_key: The secret storage manager associated with the charm.
            integrations: Information about the integrations.
            base_url: Base URL for the service.
        """
        self.framework = framework
        self._framework_config = framework_config if framework_config is not None else {}
        self._app_config = app_config if app_config is not None else {}
        self._is_secret_storage_ready = is_secret_storage_ready
        self._secret_key = secret_key
        self.integrations = integrations or IntegrationsState()
        self.base_url = base_url

    @classmethod
    def from_charm(  # pylint: disable=too-many-arguments
        cls,
        charm: ops.CharmBase,
        framework: str,
        framework_config: BaseModel,
        secret_storage: KeySecretStorage,
        base_url: str | None = None,
        integrations: "IntegrationsState | None" = None,
    ) -> "CharmState":
        """Initialize a new instance of the CharmState class from the associated charm.

        Args:
            charm: The charm instance associated with this state.
            framework: The framework name.
            framework_config: The framework specific configurations.
            base_url: Base URL for the service.
            secret_storage: The secret storage manager associated with the charm.
            integrations: State for all the Integrations.

        Return:
            The CharmState instance created by the provided charm.
        """
        app_config = {
            k.replace("-", "_"): v
            for k, v in charm.config.items()
            if not any(k.startswith(prefix) for prefix in (f"{framework}-", "webserver-", "app-"))
        }
        app_config = {
            k: v for k, v in app_config.items() if k not in framework_config.dict().keys()
        }

        return cls(
            framework=framework,
            framework_config=framework_config.dict(exclude_none=True),
            base_url=base_url,
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
    def framework_config(self) -> dict[str, str | int | bool]:
        """Get the value of the framework application specific configuration.

        Returns:
            The value of the framework application specific configuration.
        """
        return self._framework_config

    @property
    def app_config(self) -> dict[str, str | int | bool]:
        """Get the value of user-defined application configurations.

        Returns:
            The value of user-defined application configurations.
        """
        return self._app_config

    @property
    def secret_key(self) -> str:
        """Return the application secret key stored in the SecretStorage.

        It's an error to read the secret key before SecretStorage is initialized.

        Returns:
            The application secret key stored in the SecretStorage.

        Raises:
            RuntimeError: raised when accessing application secret key before
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


class IntegrationsState(BaseModel):
    """State of the integrations.

    This state is related to all the relations that can be optional, like databases, redis...

    Attrs:
        redis_uri: The redis uri provided by the redis charm.
        databases_uris: Map from interface_name to the database uri.
        s3_parameters: S3 parameters.
        saml_parameters: SAML parameters.
        rabbitmq_parameters: RabbitMQ parameters.
    """

    redis_uri: str | None = None
    databases_uris: dict[str, str] = Field(default_factory=dict)
    s3_parameters: "S3Parameters | None" = None
    saml_parameters: "SamlParameters | None" = None
    rabbitmq_parameters: "RabbitMQParameters | None" = None


class S3Parameters(BaseModel):
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
        addressing_style: S3 protocol addressing style, can be "path" or "virtual".
        attributes: The custom metadata (HTTP headers).
        tls_ca_chain: The complete CA chain, which can be used for HTTPS validation.
    """

    access_key: str = Field(alias="access-key")
    secret_key: str = Field(alias="secret-key")
    region: Optional[str] = None
    storage_class: Optional[str] = Field(alias="storage-class", default=None)
    bucket: str
    endpoint: Optional[str] = None
    path: Optional[str] = None
    s3_api_version: Optional[str] = Field(alias="s3-api-version", default=None)
    s3_uri_style: Optional[str] = Field(alias="s3-uri-style", default=None)
    tls_ca_chain: Optional[list[str]] = Field(alias="tls-ca-chain", default=None)
    attributes: Optional[list[str]] = None

    @property
    def addressing_style(self) -> Optional[str]:
        """Translates s3_uri_style to AWS addressing_style."""
        if self.s3_uri_style == "host":
            return "virtual"
        # If None or "path", it does not change.
        return self.s3_uri_style


class SamlParameters(BaseModel):
    """Configuration for accessing SAML.

    Attributes:
        entity_id: Entity Id of the SP.
        metadata_url: URL for the metadata for the SP.
        signing_certificate: Signing certificate for the SP.
        single_sign_on_redirect_url: Sign on redirect URL for the SP.
    """

    entity_id: str
    metadata_url: str
    signing_certificate: str = Field(alias="x509certs")
    single_sign_on_redirect_url: str = Field(alias="single_sign_on_service_redirect_url")

    @field_validator("signing_certificate")
    @classmethod
    def validate_signing_certificate_exists(cls, certs: str, _: ValidationInfo) -> str:
        """Validate that at least a certificate exists in the list of certificates.

        It is a prerequisite that the fist certificate is the signing certificate,
        otherwise this method would return a wrong certificate.

        Args:
            certs: Original x509certs field

        Returns:
            The validated signing certificate

        Raises:
            ValueError: If there is no certificate.
        """
        certificate = certs.split(",")[0]
        if not certificate:
            raise ValueError("Missing x509certs. There should be at least one certificate.")
        return certificate


class RabbitMQParameters(BaseModel):
    """Configuration for accessing RabbitMQ.

    Attributes:
        hostname: Hostname or ip address of broker. It could be one of the hostnames.
        hostnames: List of Hostnames or ip addresses of broker.
        username: The username to authenticate with
        password: The password to authenticate with
        vhost: RabbitMQ virtual host name.
    """

    hostname: str
    hostnames: list[str]
    username: str
    password: str
    vhost: str
