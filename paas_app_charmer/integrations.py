# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Integration interface and the implementation of integrations."""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires

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
