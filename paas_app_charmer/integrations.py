# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Integration interface and the implementation of integrations."""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class Integration(ABC):
    """Interface for integrations.

    Attributes:
        name: Name of the integration.
    """

    @abstractmethod
    def gen_environment(self) -> dict[str, str]:
        """Return the environment variables for the integration."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the integration."""

    @abstractmethod
    def block_charm(self) -> bool:
        """Return if the current state of the integration should block the charm."""


class RedisIntegration(Integration):
    """Integration for Redis.

    Attributes:
        name: Name of the integration.
    """

    def __init__(self, name: str, redis_url: Optional[str], optional: bool):
        """Initialize a new instance of the RedisIntegration class.

        Args:
            name: Name of the integration.
            redis_url: Redis url.
            optional: If the integration is optional
        """
        self._name = name
        self._optional = optional
        self._redis_url = redis_url

    @property
    def name(self) -> str:
        """Return the name of the integration."""
        return self._name

    def gen_environment(self) -> dict[str, str]:
        """Return the environment variables for the Redis integration.

        Returns: Environment variables.
        """
        if self._redis_url:
            return {"REDIS_DB_CONNECT_STRING": self._redis_url}
        return {}

    def block_charm(self) -> bool:
        """Return if the current state of the integration should block the charm.

        Returns:
           Whether to block the charm if the integration is not ready.
        """
        return not self._optional and not self.gen_environment()


class DatabaseIntegration(Integration):
    """Integration for Database (postgresql, mysql and mongodb).

    Attributes:
        name: Name of the integration.
    """

    def __init__(self, name: str, database_requires: DatabaseRequires, optional: bool):
        """Initialize a new instance of the DatabaseIntegration class.

        Args:
            name: Name of the integration.
            database_requires: DatabaseRequires object
            optional: If the integration is optional
        """
        self._name = name
        self._database_requires = database_requires
        self._optional = optional

    @property
    def name(self) -> str:
        """Return the name of the integration."""
        return self._name

    def gen_environment(self) -> dict[str, str]:
        """Return the environment variables for the Database integration.

        Returns: Environment variables.
        """
        relation_data = list(
            self._database_requires.fetch_relation_data(
                fields=["uris", "endpoints", "username", "password", "database"]
            ).values()
        )
        if not relation_data:
            return {}

        # There can be only one database integrated at a time
        # with the same interface name. See: metadata.yaml
        data = relation_data[0]

        env_name = f"{self._name.upper()}_DB_CONNECT_STRING"

        if "uris" in data:
            return {env_name: data["uris"]}

        # Check that the relation data is well formed according to the following json_schema:
        # https://github.com/canonical/charm-relation-interfaces/blob/main/interfaces/mysql_client/v0/schemas/provider.json
        if not all(data.get(key) for key in ("endpoints", "username", "password")):
            logger.warning("Incorrect relation data from the data provider: %s", data)
            return {}

        database_name = data.get("database", self._database_requires.database)
        endpoint = data["endpoints"].split(",")[0]
        return {
            env_name: (
                f"{self._name}://"
                f"{data['username']}:{data['password']}"
                f"@{endpoint}/{database_name}"
            )
        }

    def block_charm(self) -> bool:
        """Return if the current state of the integration should block the charm.

        Returns:
           Whether to block the charm if the integration is not ready.
        """
        return not self._optional and not self.gen_environment()


class S3Integration(Integration):
    """Integration for S3.

    Attributes:
        name: Name of the integration.
    """

    def __init__(self, name: str, s3_connection_info: dict[str, str], optional: bool):
        """Initialize a new instance of the S3Integration class.

        Args:
            name: Name of the integration.
            s3_connection_info: ??
            optional: If the integration is optional.
        """
        self._name = name
        self._s3_connection_info = s3_connection_info
        self._optional = optional

    @property
    def name(self) -> str:
        """Return the name of the integration."""
        return self._name

    def gen_environment(self) -> dict[str, str]:
        """Return the environment variables for the Database integration.

        Returns: Environment variables.
        """
        try:
            s3 = S3Parameters(**self._s3_connection_info)
        except ValidationError:
            return {}
        env_vars = {
            "S3_ACCESS_KEY": s3.access_key,
            "S3_SECRET_KEY": s3.secret_key,
            "S3_REGION": s3.region,
            "S3_STORAGE_CLASS": s3.storage_class,
            "S3_BUCKET": s3.bucket,
            "S3_ENDPOINT": s3.endpoint,
            "S3_PATH": s3.path,
            "S3_API_VERSION": s3.s3_api_version,
            "S3_URI_STYLE": s3.s3_uri_style,
            "S3_TLS_CA_CHAIN": s3.tls_ca_chain,
            "S3_ADDRESSING_STYLE": s3.addressing_style,
        }
        return {k: v for k, v in env_vars.items() if v is not None}

    def block_charm(self) -> bool:
        """Return if the current state of the integration should block the charm.

        Returns:
           Whether to block the charm if the integration is not ready.
        """
        return not self._optional and not self.gen_environment()


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
        tls_ca_chain: The complete CA chain, which can be used for HTTPS validation.
        addressing_style: S3 protocol addressing style, can be "path" or "virtual".
        attributes: The custom metadata (HTTP headers).
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
    tls_ca_chain: Optional[str] = Field(alias="tls-ca-chain", default=None)
    attributes: Optional[str] = None

    @property
    def addressing_style(self) -> Optional[str]:
        """Translates s3_uri_style to AWS addressing_style."""
        if self.s3_uri_style == "host":
            return "virtual"
        # If None or "path", it does not change.
        return self.s3_uri_style
