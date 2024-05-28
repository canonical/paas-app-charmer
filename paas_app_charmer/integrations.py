# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Classes that provide the required integrations functionality."""

import logging
from abc import ABC, abstractmethod

from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires

logger = logging.getLogger(__name__)


class Integration(ABC):
    """TODO.

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

    def block_charm(self) -> bool:
        """Return if the current state of the integration should block the charm.

        Returns:
           TODO.
        """
        return False


class GenericIntegration(Integration):
    """TODO.

    Attributes:
        name: Name of the integration.
    """

    def __init__(self, name: str, blocks: bool, env_vars: dict[str, str]):
        """TODO.

        Args:
            name: name
            blocks: blocks
            env_vars: env_vars
        """
        self._name = name
        self._blocks = blocks
        self._env_vars = env_vars

    @property
    def name(self) -> str:
        """TODO."""
        return self._name

    def gen_environment(self) -> dict[str, str]:
        """TODO.

        Returns: TODO
        """
        return self._env_vars

    def block_charm(self) -> bool:
        """TODO.

        Returns: TODO
        """
        return self._blocks


class DatabaseIntegration(Integration):
    """TODO.

    Attributes:
        name: Name of the integration.
    """

    def __init__(self, interface_name: str, database_requires: DatabaseRequires):
        """TODO.

        Args:
            interface_name: TODO
            database_requires: TODO
        """
        self._interface_name = interface_name
        self._database_requires = database_requires

    @property
    def name(self) -> str:
        """TODO."""
        return self._interface_name

    def gen_environment(self) -> dict[str, str]:
        """TODO.

        Returns: TODO
        """
        # remove databases.get_uris function
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

        env_name = f"{self._interface_name.upper()}_DB_CONNECT_STRING"

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
                f"{self._interface_name}://"
                f"{data['username']}:{data['password']}"
                f"@{endpoint}/{database_name}"
            )
        }
