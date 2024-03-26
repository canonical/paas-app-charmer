# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Databases class to handle database relations and state."""

import logging
import pathlib
import typing

import ops
import yaml
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires

SUPPORTED_DB_INTERFACES = {
    "mysql_client": "mysql",
    "postgresql_client": "postgresql",
    "mongodb_client": "mongodb",
    "redis": "redis",
}

logger = logging.getLogger(__name__)


class Application(typing.Protocol):  # pylint: disable=too-few-public-methods
    """Interface for the charm managed application."""

    def restart(self) -> None:
        """Restart the application."""


class _RedisDatabaseRequiresShim:  # pylint: disable=too-few-public-methods
    """A shim to allow handling redis relation similar to other data platform databases."""

    class _RedisDatabaseRequiresEventShim:  # pylint: disable=too-few-public-methods
        """A shim to provide redis database_created event as in the DatabaseRequires."""

        def __init__(self, relation_changed: typing.Callable):
            """Initialize the _RedisDatabaseRequiresEventShim object.

            As we are checking the database relation later in the get_uris function.
            We can use the charm's relation_changed event as database_created and
            endpoints_changed event.

            Args:
                relation_changed: charm's redis relation changed event.
            """
            self.database_created = relation_changed
            self.endpoints_changed = relation_changed

    def __init__(self, charm: ops.CharmBase, relation_name: str):
        """Initialize the redis database requires.

        Args:
            charm: The requesting charm object.
            relation_name: The redis relation name.
        """
        self._charm = charm
        self.relation_name = relation_name
        # redis charm doesn't provide database id via the relation
        self.database = ""
        self.on = self._RedisDatabaseRequiresEventShim(
            self._charm.on[relation_name].relation_changed
        )

    def fetch_relation_data(
        self, fields: typing.List[str]
    ) -> typing.Dict[int, typing.Dict[str, str]]:
        """Mimic the fetch_relation_data method of DatabaseRequires class.

        Args:
            fields: fields to fetch from relation data.

        Returns: required relation data.
        """
        data = {}
        for relation in self._charm.model.relations[self.relation_name]:
            endpoints = []
            if relation.app is None:
                continue
            for unit in relation.units:
                if not (hostname := relation.data[unit].get("hostname")):
                    continue
                if not (port := relation.data[unit].get("port")):
                    continue
                endpoints.append(f"{hostname}:{port}")
            if endpoints:
                data[relation.id] = (
                    {"endpoints": ",".join(endpoints)} if "endpoints" in fields else {}
                )
        return data


def make_database_requirers(
    charm: ops.CharmBase, database_name: str
) -> typing.Dict[str, DatabaseRequires]:
    """Create database requirer objects for the charm.

    Args:
        charm: The requiring charm.
        database_name: the required database name

    Returns: A dictionary which is the database uri environment variable name and the
        value is the corresponding database requirer object.
    """
    metadata_file = pathlib.Path("metadata.yaml")
    if not metadata_file.exists():
        metadata_file = pathlib.Path("charmcraft.yaml")
    metadata = yaml.safe_load(metadata_file.read_text(encoding="utf-8"))
    db_interfaces = (
        SUPPORTED_DB_INTERFACES[require["interface"]]
        for require in metadata["requires"].values()
        if require["interface"] in SUPPORTED_DB_INTERFACES
    )
    # automatically create database relation requirers to manage database relations
    # one database relation requirer is required for each of the database relations
    # create a dictionary to hold the requirers
    databases = {
        name: (
            DatabaseRequires(
                charm,
                relation_name=name,
                database_name=database_name,
            )
            if name != "redis"
            else _RedisDatabaseRequiresShim(charm, relation_name=name)
        )
        for name in db_interfaces
    }
    return databases


def get_uris(database_requirers: typing.Dict[str, DatabaseRequires]) -> typing.Dict[str, str]:
    """Compute DatabaseURI and return it.

    Args:
        database_requirers: Database requirers created by make_database_requirers.

    Returns:
        DatabaseURI containing details about the data provider integration
    """
    db_uris: typing.Dict[str, str] = {}

    for interface_name, db_requires in database_requirers.items():
        relation_data = list(
            db_requires.fetch_relation_data(
                fields=["uris", "endpoints", "username", "password", "database"]
            ).values()
        )

        if not relation_data:
            continue

        # There can be only one database integrated at a time
        # with the same interface name. See: metadata.yaml
        data = relation_data[0]

        env_name = f"{interface_name.upper()}_DB_CONNECT_STRING"

        if interface_name == "redis":
            endpoint = data["endpoints"].split(",")[0]
            db_uris[env_name] = f"{interface_name}://{endpoint}"
        if "uris" in data:
            db_uris[env_name] = data["uris"]
            continue

        # Check that the relation data is well formed according to the following json_schema:
        # https://github.com/canonical/charm-relation-interfaces/blob/main/interfaces/mysql_client/v0/schemas/provider.json
        if not all(data.get(key) for key in ("endpoints", "username", "password")):
            logger.warning("Incorrect relation data from the data provider: %s", data)
            continue

        database_name = data.get("database", db_requires.database)
        endpoint = data["endpoints"].split(",")[0]
        db_uris[env_name] = (
            f"{interface_name}://"
            f"{data['username']}:{data['password']}"
            f"@{endpoint}/{database_name}"
        )

    return db_uris


# We need to derive from ops.framework.Object to subscribe to callbacks
# from ops.framework. See: https://github.com/canonical/operator/blob/main/ops/framework.py#L782
class Databases(ops.Object):  # pylint: disable=too-few-public-methods
    """A class handling databases relations and state.

    Attrs:
        _charm: The main charm. Used for events callbacks
        _databases: A dict of DatabaseRequires to store relations
    """

    def __init__(
        self,
        charm: ops.CharmBase,
        application: Application,
        database_requirers: typing.Dict[str, DatabaseRequires],
    ):
        """Initialize a new instance of the Databases class.

        Args:
            charm: The main charm. Used for events callbacks.
            application: The application manager object.
            database_requirers: Database requirers created by make_database_requirers.
        """
        # The following is necessary to be able to subscribe to callbacks from ops.framework
        super().__init__(charm, "databases")
        self._charm = charm
        self._application = application
        self._databases = database_requirers
