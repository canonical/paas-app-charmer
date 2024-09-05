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

from paas_app_charmer.charm_state import IntegrationsState, S3Parameters, SamlParameters
from paas_app_charmer.exceptions import CharmConfigInvalidError
from paas_app_charmer.rabbitmq import RabbitMQRequires
from paas_app_charmer.utils import build_validation_error_message

logger = logging.getLogger(__name__)


class Integrations:  # pylint: disable=too-many-instance-attributes
    """TODO."""

    def __init__(self, charm: ops.CharmBase) -> None:
        """TODO.

        Args:
            charm: TODO
        """
        self._charm = charm
        self._mysql = Database(charm, "mysql", "mysql_client")
        self._postgresql = Database(charm, "postgresql", "postgresql_client")
        self._mongodb = Database(charm, "mongodb", "mongodb_client")
        self._redis = Redis(charm)
        self._s3 = S3(charm)
        self._saml = Saml(charm)
        self._rabbitmq = RabbitMQ(charm)
        self._databases: list[Database] = [self._mysql, self._postgresql, self._mongodb]
        self._integrations: list[Integration] = [
            self._mysql,
            self._postgresql,
            self._mongodb,
            self._redis,
            self._s3,
            self._saml,
            self._rabbitmq,
        ]

    def register(self, callback: Callable[[Any], None]) -> None:
        """TODO.

        Args:
            callback: TODO
        """
        for integration in self._integrations:
            integration.register(callback)

    def missing_integrations(self) -> list[str]:
        """TODO.

        Returns:
            TODO.
        """
        return [
            integration.name for integration in self._integrations if not integration.is_ready()
        ]

    def databases_uris(self) -> dict[str, str]:
        """TODO.

        Returns:
            TODO.
        """
        return dict(
            (k, v) for k, v in ((db.name, db.get_uri()) for db in self._databases) if v is not None
        )

    def create_integrations_state(self) -> IntegrationsState:
        """TODO.

        can raise.

        Returns:
            TODO.
        """
        return IntegrationsState.build(
            redis_uri=self._redis.get_url(),
            database_uris=self.databases_uris(),
            s3_connection_info=self._s3.get_connection_info(),
            saml_relation_data=self._saml.get_relation_data(),
            rabbitmq_parameters=self._rabbitmq.parameters(),
        )


class Integration(ABC):
    """TODO.

    Attributes:
        name: TODO
        interface_name: TODO
    """

    name: str
    interface_name: str

    def __init__(self, charm: ops.CharmBase):
        """TODO.

        Args:
            charm: TODO
        """
        self._charm = charm
        self._framework = self._charm.framework

    @abstractmethod
    def register(self, callback: Callable[[Any], None]) -> None:
        """TODO.

        Args:
            callback: TODO
        """

    @abstractmethod
    def is_ready(self) -> bool:
        """TODO."""

    def _is_defined(self) -> bool:
        """TODO.

        Returns:
            TODO.
        """
        requires = self._framework.meta.requires
        if self.name in requires and requires[self.name].interface_name == self.interface_name:
            return True
        return False

    def _is_optional(self) -> bool:
        """TODO.

        Returns:
            TODO.
        """
        requires = self._framework.meta.requires
        if requires[self.name] and requires[self.name].optional:
            return True
        return False


class Database(Integration):
    """TODO."""

    def __init__(self, charm: ops.CharmBase, name: str, interface_name: str) -> None:
        """TODO.

        Args:
            charm: TODO
            name: TODO
            interface_name: TODO
        """
        super().__init__(charm)
        self.name = name
        self.interface_name = interface_name
        self._database_requires: DatabaseRequires | None = None

    def register(self, callback: Callable[[Any], None]) -> None:
        """TODO.

        Args:
            callback: TODO
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
        """TODO.

        Returns:
            TODO
        """
        if self._is_defined() and not self._is_optional() and not self.parameters():
            return False
        return True

    def get_uri(self) -> str | None:
        """TODO.

        Returns:
            TODO
        """
        if self._database_requires:
            return get_database_uri(self._database_requires)
        return None

    # returns a str, not good...
    def parameters(self) -> str | None:
        """TODO.

        Returns:
            TODO
        """
        return self.get_uri()


class Redis(Integration):
    """TODO."""

    def __init__(self, charm: ops.CharmBase):
        """TODO.

        Args:
            charm: TODO
        """
        super().__init__(charm)
        self.name = "redis"
        self.interface_name = "redis"
        self._redis: RedisRequires | None = None

    def register(self, callback: Callable[[Any], None]) -> None:
        """TODO.

        Args:
            callback: TODO
        """
        if self._is_defined():
            self._redis = RedisRequires(charm=self._charm, relation_name="redis")
            self._framework.observe(self._charm.on.redis_relation_updated, callback)

    def is_ready(self) -> bool:
        """TODO.

        Returns:
            TODO
        """
        if self._is_defined() and not self._is_optional() and not self.get_url():
            return False
        return True

    def get_url(self) -> str | None:
        """TODO.

        Returns:
            TODO
        """
        redis_uri = self._redis.url if self._redis else None
        # Workaround as the Redis library temporarily sends the port
        # as None while the integration is being created.
        if redis_uri is not None and re.fullmatch(r"redis://[^:/]+:None", redis_uri):
            redis_uri = None
        return redis_uri


class S3(Integration):
    """TODO."""

    def __init__(self, charm: ops.CharmBase):
        """TODO.

        Args:
            charm: TODO
        """
        super().__init__(charm)
        self.name = "s3"
        self.interface_name = "s3"
        self._s3 = None

    def _is_defined(self) -> bool:
        """TODO.

        Returns:
            TODO.
        """
        try:
            # pylint: disable=ungrouped-imports,import-outside-toplevel,unused-import
            import charms.data_platform_libs.v0.s3  # noqa: F401
        except ImportError:
            return False

        return super()._is_defined()

    def register(self, callback: Callable[[Any], None]) -> None:
        """TODO.

        Args:
            callback: TODO
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
        """TODO.

        Returns:
            TODO
        """
        if self._s3 is not None:
            return self._s3.get_s3_connection_info()
        return None

    def get_parameters(self) -> S3Parameters | None:
        """TODO.

        Returns:
            TODO

        Raises:
            CharmConfigInvalidError: If there is connection info but parameters are invalid.
        """
        s3_parameters = None
        s3_connection_info = self.get_connection_info()
        if s3_connection_info:
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
        """TODO.

        This can raise. TODO is this good? should we protect?

        Returns:
            TODO
        """
        if self._is_defined() and not self._is_optional() and not self.get_parameters():
            return False
        return True


class Saml(Integration):
    """TODO."""

    def __init__(self, charm: ops.CharmBase):
        """TODO.

        Args:
            charm: TODO
        """
        super().__init__(charm)
        self.name = "saml"
        self.interface_name = "saml"
        self._saml = None

    def _is_defined(self) -> bool:
        """TODO.

        Returns:
            TODO.
        """
        try:
            # pylint: disable=ungrouped-imports,import-outside-toplevel,unused-import
            import charms.saml_integrator.v0.saml  # noqa: F401
        except ImportError:
            return False

        return super()._is_defined()

    def register(self, callback: Callable[[Any], None]) -> None:
        """TODO.

        Args:
            callback: TODO
        """
        if self._is_defined():
            # pylint: disable=import-outside-toplevel
            from charms.saml_integrator.v0.saml import SamlRequires

            saml = SamlRequires(self._charm)
            self._framework.observe(saml.on.saml_data_available, callback)
            self._saml = saml

    def get_relation_data(self) -> Dict[str, str] | None:
        """TODO.

        Returns:
            TODO
        """
        if self._saml is not None:
            relation_data = self._saml.get_relation_data()
            if relation_data:
                return dict(relation_data.to_relation_data())
        return None

    def get_parameters(self) -> SamlParameters | None:
        """TODO.

        Returns:
            TODO

        Raises:
            CharmConfigInvalidError: If there is connection info but parameters are invalid.
        """
        saml_parameters = None
        saml_relation_data = self.get_relation_data()
        if saml_relation_data:
            try:
                saml_parameters = SamlParameters(**saml_relation_data)
            except ValidationError as exc:
                error_message = build_validation_error_message(exc)
                raise CharmConfigInvalidError(
                    f"Invalid Saml configuration: {error_message}"
                ) from exc
        return saml_parameters

    def is_ready(self) -> bool:
        """TODO.

        This can raise. TODO is this good? should we protect?

        Returns:
            TODO
        """
        if self._is_defined() and not self._is_optional() and not self.get_parameters():
            return False
        return True


class RabbitMQ(Integration):
    """TODO."""

    def __init__(self, charm: ops.CharmBase):
        """TODO.

        Args:
            charm: TODO
        """
        super().__init__(charm)
        self.name = "amqp"
        self.interface_name = "rabbitmq"
        self._amqp: RabbitMQRequires | None = None

    def register(self, callback: Callable[[Any], None]) -> None:
        """TODO.

        Args:
            callback: TODO
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
        """TODO.

        Returns:
            TODO
        """
        if self._is_defined() and not self._is_optional() and not self.parameters():
            return False
        return True

    # returns a RabbitMQ(BaseModel), not good...
    def parameters(self) -> Any:
        """TODO.

        Returns:
            TODO
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
