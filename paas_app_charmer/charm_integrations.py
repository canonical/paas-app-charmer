# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm integrations."""

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from charms.redis_k8s.v0.redis import RedisRequires
from pydantic import ValidationError

from paas_app_charmer.charm_state import (
    IntegrationsState,
    RabbitMQParameters,
    S3Parameters,
    SamlParameters,
)
from paas_app_charmer.exceptions import CharmConfigInvalidError
from paas_app_charmer.rabbitmq import RabbitMQRequires
from paas_app_charmer.utils import build_validation_error_message

logger = logging.getLogger(__name__)


class Integrations:
    """Manages Charm Integrations for the Charm."""

    def __init__(self, charm: ops.CharmBase) -> None:
        """Initialise the instance.

        Args:
            charm: The charm instance managed by this instance.
        """
        self._charm = charm
        self._redis = Redis(charm)
        self._s3 = S3(charm)
        self._saml = Saml(charm)
        self._rabbitmq = RabbitMQ(charm)
        self._databases: list[Database] = [
            Database(charm, "mysql", "mysql_client"),
            Database(charm, "postgresql", "postgresql_client"),
            Database(charm, "mongodb", "mongodb_client"),
        ]
        self._integrations: list[Integration] = [
            *self._databases,
            self._redis,
            self._s3,
            self._saml,
            self._rabbitmq,
        ]

    def register(self, callback: Callable[[Any], None]) -> None:
        """Register all the integrations using the same callback if necessary.

        Args:
            callback: Callback function for the hooks
        """
        for integration in self._integrations:
            integration.register(callback)

    def missing_integrations(self) -> list[str]:
        """Return a list of integrations that are not optional and are missing.

        Returns:
            list of missing integrations.
        """
        return [
            integration.name for integration in self._integrations if not integration.is_ready()
        ]

    def databases_uris(self) -> dict[str, str]:
        """Return of database names to uris.

        Returns:
            dict of database names to uris.
        """
        return dict(
            (k, v) for k, v in ((db.name, db.get_uri()) for db in self._databases) if v is not None
        )

    def create_integrations_state(self) -> IntegrationsState:
        """Create the IntegrationState.

        Can raise CharmConfigInvalidError if some data is invalid for an integration

        Returns:
            IntegrationState with current integrations.
        """
        return IntegrationsState(
            redis_uri=self._redis.get_url(),
            databases_uris=self.databases_uris(),
            s3_parameters=self._s3.get_parameters(),
            saml_parameters=self._saml.get_parameters(),
            rabbitmq_parameters=self._rabbitmq.get_parameters(),
        )


class Integration(ABC):
    """Base class for an integration."""

    def __init__(self, charm: ops.CharmBase, name: str, interface_name: str):
        """Initialise the instance.

        Args:
            charm: The charm instance managed by this instance.
            name: name of the endpoint as in charmcraft.yaml.
            interface_name: name of the interface as in charmcraft.yaml.
        """
        self._charm = charm
        self._framework = self._charm.framework
        self.name = name
        self.interface_name = interface_name

    @abstractmethod
    def register(self, callback: Callable[[Any], None]) -> None:
        """Register all the observers.

        Args:
            callback: Callback function for the hooks
        """

    @abstractmethod
    def is_ready(self) -> bool:
        """Check if the integration is ready."""

    def _is_defined(self) -> bool:
        """Check if the integration is defined in charmcraft.yaml.

        Returns:
            True if the integration is defined in charmcraft.yaml.
        """
        requires = self._framework.meta.requires
        if self.name in requires and requires[self.name].interface_name == self.interface_name:
            return True
        return False

    def _is_optional(self) -> bool:
        """Check if the integration is optional (and defined)  in charmcraft.yaml.

        Returns:
            True if the integration is optional in charmcraft.yaml.
        """
        requires = self._framework.meta.requires
        if requires[self.name] and requires[self.name].optional:
            return True
        return False


class Database(Integration):
    """Manage database Integration for the charm."""

    def __init__(self, charm: ops.CharmBase, name: str, interface_name: str) -> None:
        """Initialise the instance.

        Args:
            charm: The charm instance managed by this instance.
            name: name of the endpoint as in charmcraft.yaml.
            interface_name: name of the interface as in charmcraft.yaml.
        """
        super().__init__(charm, name, interface_name)
        self._database_requires: DatabaseRequires | None = None

    def register(self, callback: Callable[[Any], None]) -> None:
        """Register all the observers.

        Args:
            callback: Callback function for the hooks
        """
        if self._is_defined():
            self._database_requires = DatabaseRequires(
                self._charm,
                relation_name=self.name,
                database_name=self._charm.app.name,
            )
            self._framework.observe(self._database_requires.on.database_created, callback)
            self._framework.observe(self._database_requires.on.endpoints_changed, callback)
            self._framework.observe(
                self._charm.on[self._database_requires.relation_name].relation_broken,
                callback,
            )

    def is_ready(self) -> bool:
        """Check if the integration is ready.

        Returns:
            True if the integration is ready.
        """
        return not self._is_defined() or self._is_optional() or self.get_uri() is not None

    def get_uri(self) -> str | None:
        """Get URI for the database.

        Returns:
            URI for the database
        """
        if self._database_requires:
            return get_database_uri(self._database_requires)
        return None


class Redis(Integration):
    """Manage Redis Integration for the charm."""

    def __init__(self, charm: ops.CharmBase):
        """Initialise the instance.

        Args:
            charm: The charm instance managed by this instance.
        """
        super().__init__(charm, "redis", "redis")
        self._redis: RedisRequires | None = None

    def register(self, callback: Callable[[Any], None]) -> None:
        """Register all the observers.

        Args:
            callback: Callback function for the hooks
        """
        if self._is_defined():
            self._redis = RedisRequires(charm=self._charm, relation_name="redis")
            self._framework.observe(self._charm.on.redis_relation_updated, callback)

    def is_ready(self) -> bool:
        """Check if the integration is ready.

        Returns:
            True if the integration is ready.
        """
        return not self._is_defined() or self._is_optional() or self.get_url() is not None

    def get_url(self) -> str | None:
        """Get URL for the Redis instance.

        Returns:
            URL for the Redis instance
        """
        redis_uri = self._redis.url if self._redis else None
        # Workaround as the Redis library temporarily sends the port
        # as None while the integration is being created.
        if redis_uri is not None and re.fullmatch(r"redis://[^:/]+:None", redis_uri):
            redis_uri = None
        return redis_uri


class S3(Integration):
    """Manage S3 Integration for the charm."""

    def __init__(self, charm: ops.CharmBase):
        """Initialise the instance.

        Args:
            charm: The charm instance managed by this instance.
        """
        super().__init__(charm, "s3", "s3")
        # cannot import S3Requirer in here, as it may fail if the lib is missing.
        self._s3: Any = None

    def _is_defined(self) -> bool:
        """Check if the integration is defined in charmcraft.yaml.

        It will return False also if there is no library for the integration.

        Returns:
            True if the integration is defined in charmcraft.yaml.
        """
        try:
            # pylint: disable=ungrouped-imports,import-outside-toplevel,unused-import
            import charms.data_platform_libs.v0.s3  # noqa: F401
        except ImportError:
            return False

        return super()._is_defined()

    def register(self, callback: Callable[[Any], None]) -> None:
        """Register all the observers.

        Args:
            callback: Callback function for the hooks
        """
        if self._is_defined():
            # pylint: disable=import-outside-toplevel
            from charms.data_platform_libs.v0.s3 import S3Requirer

            s3 = S3Requirer(
                charm=self._charm, relation_name=self.name, bucket_name=self._charm.app.name
            )
            self._framework.observe(s3.on.credentials_changed, callback)
            self._framework.observe(s3.on.credentials_gone, callback)
            self._s3 = s3

    def get_connection_info(self) -> Dict[str, str] | None:
        """Return connection Info from the S3 library.

        Returns:
            connection info dictionary.
        """
        return self._s3.get_s3_connection_info() if self._s3 is not None else None

    def get_parameters(self) -> S3Parameters | None:
        """Build S3Parameters from the S3 relation.

        Returns:
            S3Paramaeters or None if there is no S3 relation.

        Raises:
            CharmConfigInvalidError: If there is connection info but parameters are invalid.
        """
        s3_parameters = None
        if s3_connection_info := self.get_connection_info():
            try:
                # s3_connection_info is not really a Dict[str, str] as stated in
                # charms.data_platform_libs.v0.s3. It is really a
                # Dict[str, str | list[str]].
                # Ignoring as mypy does not work correctly with that information.
                s3_parameters = S3Parameters(**s3_connection_info)  # type: ignore[arg-type]
            except ValidationError as exc:
                error_message = build_validation_error_message(exc)
                raise CharmConfigInvalidError(
                    f"Invalid S3 configuration: {error_message}"
                ) from exc
        return s3_parameters

    def is_ready(self) -> bool:
        """Check if the integration is ready.

        Returns:
            True if the integration is ready.
        """
        return not self._is_defined() or self._is_optional() or self.get_parameters() is not None


class Saml(Integration):
    """Manage SAML Integration for the charm."""

    def __init__(self, charm: ops.CharmBase):
        """Initialise the instance.

        Args:
            charm: The charm instance managed by this instance.
        """
        super().__init__(charm, "saml", "saml")
        self._saml = None

    def _is_defined(self) -> bool:
        """Check if the integration is defined in charmcraft.yaml.

        It will return False also if there is no library for the integration.

        Returns:
            True if the integration is defined in charmcraft.yaml.
        """
        try:
            # pylint: disable=ungrouped-imports,import-outside-toplevel,unused-import
            import charms.saml_integrator.v0.saml  # noqa: F401
        except ImportError:
            return False

        return super()._is_defined()

    def register(self, callback: Callable[[Any], None]) -> None:
        """Register all the observers.

        Args:
            callback: Callback function for the hooks
        """
        if self._is_defined():
            # pylint: disable=import-outside-toplevel
            from charms.saml_integrator.v0.saml import SamlRequires

            saml = SamlRequires(self._charm)
            self._framework.observe(saml.on.saml_data_available, callback)
            self._saml = saml

    def get_relation_data(self) -> Dict[str, str] | None:
        """Get relation data from SAML library.

        Returns:
            dict of relation data for SAML or None
        """
        if self._saml is not None:
            relation_data = self._saml.get_relation_data()
            if relation_data:
                return dict(relation_data.to_relation_data())
        return None

    def get_parameters(self) -> SamlParameters | None:
        """Build SamlParameters from the SAML relation.

        Returns:
            SamlParameters or None if there is no SAML relation.

        Raises:
            CharmConfigInvalidError: If there is connection info but parameters are invalid.
        """
        saml_parameters = None
        saml_relation_data = self.get_relation_data()
        if saml_relation_data is not None:
            try:
                saml_parameters = SamlParameters(**saml_relation_data)
            except ValidationError as exc:
                error_message = build_validation_error_message(exc)
                raise CharmConfigInvalidError(
                    f"Invalid Saml configuration: {error_message}"
                ) from exc
        return saml_parameters

    def is_ready(self) -> bool:
        """Check if the integration is ready.

        Returns:
            True if the integration is ready.
        """
        return not self._is_defined() or self._is_optional() or self.get_parameters() is not None


class RabbitMQ(Integration):
    """Manage RabbitMQ Integration for the charm."""

    def __init__(self, charm: ops.CharmBase):
        """Initialise the instance.

        Args:
            charm: The charm instance managed by this instance.
        """
        super().__init__(charm, "amqp", "rabbitmq")
        self._amqp: RabbitMQRequires | None = None

    def register(self, callback: Callable[[Any], None]) -> None:
        """Register all the observers.

        Args:
            callback: Callback function for the hooks
        """
        if self._is_defined():
            self._amqp = RabbitMQRequires(
                self._charm,
                self.name,
                username=self._charm.app.name,
                vhost="/",
            )
            self._framework.observe(self._amqp.on.connected, callback)
            self._framework.observe(self._amqp.on.ready, callback)
            self._framework.observe(self._amqp.on.goneaway, callback)

    def is_ready(self) -> bool:
        """Check if the integration is ready.

        Returns:
            True if the integration is ready.
        """
        return not self._is_defined() or self._is_optional() or self.get_parameters() is not None

    def get_parameters(self) -> RabbitMQParameters | None:
        """Build RabbitMQParameters from the RabbitMQ relation.

        Returns:
            RabbitMQParameters or None if there is no RabbitMQ relation.
        """
        return self._amqp.rabbitmq_parameters() if self._amqp else None


def get_database_uri(database_requires: DatabaseRequires) -> str | None:
    """Compute a URI for DatabaseRequires and return it.

    Args:
        database_requires: DatabaseRequires object from the data platform.

    Returns:
        uri for the database of None if the uri could not be built.
    """
    relation_data = list(
        database_requires.fetch_relation_data(
            fields=["uris", "endpoints", "username", "password", "database"]
        ).values()
    )

    if not relation_data:
        return None

    # There can be only one database integrated at a time
    # with the same interface name. See: metadata.yaml
    data = relation_data[0]

    if "uris" in data:
        return data["uris"]

    # Check that the relation data is well formed according to the following json_schema:
    # https://github.com/canonical/charm-relation-interfaces/blob/main/interfaces/mysql_client/v0/schemas/provider.json
    if not all(data.get(key) for key in ("endpoints", "username", "password")):
        logger.warning("Incorrect relation data from the data provider: %s", data)
        return None

    database_name = data.get("database", database_requires.database)
    endpoint = data["endpoints"].split(",")[0]
    return (
        f"{database_requires.relation_name}://"
        f"{data['username']}:{data['password']}"
        f"@{endpoint}/{database_name}"
    )
