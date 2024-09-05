# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""RabbitMQ library for handling the rabbitmq interface.

The project https://github.com/openstack-charmers/charm-rabbitmq-k8s provides
a library for the requires part of the rabbitmq interface.

However, there are two charms that provide the rabbitmq interface, being incompatible:
 - https://github.com/openstack-charmers/charm-rabbitmq-ks8 (https://charmhub.io/rabbitmq-k8s)
 - https://github.com/openstack/charm-rabbitmq-server/ (https://charmhub.io/rabbitmq-server)

The main difference is that rabbitmq-server does not publish the information in the app
part in the relation bag. This python library unifies both charms, using a similar
approach to the rabbitmq-k8s library.

For rabbitmq-k8s, the password and hostname are required in the app databag. The full
list of hostnames can be obtained from the ingress-address in each unit.

For rabbitmq-server, the app databag is empty. The password and hostname are in the units databags,
being the password equal in all units. Each hostname may point to different addresses. One
of them will chosen as the in the rabbitmq parameters.

rabbitmq-server support ssl client certificates, but are not implemented in this library.

This library is very similar and uses the same events as
 the library charms.rabbitmq_k8s.v0.rabbitmq.
See https://github.com/openstack-charmers/charm-rabbitmq-k8s/blob/main/lib/charms/rabbitmq_k8s/v0/rabbitmq.py  # pylint: disable=line-too-long # noqa: W505
"""


import logging

from ops import CharmBase, HookEvent
from ops.framework import EventBase, EventSource, Object, ObjectEvents
from ops.model import Relation

from paas_app_charmer.charm_state import RabbitMQParameters

logger = logging.getLogger(__name__)


class RabbitMQConnectedEvent(EventBase):
    """RabbitMQ connected Event."""


class RabbitMQReadyEvent(EventBase):
    """RabbitMQ ready for use Event."""


class RabbitMQGoneAwayEvent(EventBase):
    """RabbitMQ relation has gone-away Event."""


class RabbitMQServerEvents(ObjectEvents):
    """Events class for `on`.

    Attributes:
        connected: rabbitmq relation is connected
        ready: rabbitmq relation is ready
        goneaway: rabbitmq relation has been removed
    """

    connected = EventSource(RabbitMQConnectedEvent)
    ready = EventSource(RabbitMQReadyEvent)
    goneaway = EventSource(RabbitMQGoneAwayEvent)


class RabbitMQRequires(Object):
    """RabbitMQRequires class.

    Attributes:
        on: ObjectEvents for RabbitMQRequires
    """

    on = RabbitMQServerEvents()

    def __init__(self, charm: CharmBase, relation_name: str, username: str, vhost: str):
        """Initialize the instance.

        Args:
           charm: charm that uses the library
           relation_name: name of the RabbitMQ relation
           username: username to use for RabbitMQ
           vhost: virtual host to use for RabbitMQ
        """
        super().__init__(charm, relation_name)
        self.charm = charm
        self.relation_name = relation_name
        self.username = username
        self.vhost = vhost
        self.framework.observe(
            self.charm.on[relation_name].relation_joined,
            self._on_rabbitmq_relation_joined,
        )
        self.framework.observe(
            self.charm.on[relation_name].relation_changed,
            self._on_rabbitmq_relation_changed,
        )
        self.framework.observe(
            self.charm.on[relation_name].relation_departed,
            self._on_rabbitmq_relation_changed,
        )
        self.framework.observe(
            self.charm.on[relation_name].relation_broken,
            self._on_rabbitmq_relation_broken,
        )

    def _on_rabbitmq_relation_joined(self, _: HookEvent) -> None:
        """Handle RabbitMQ joined."""
        self.on.connected.emit()
        self.request_access(self.username, self.vhost)

    def _on_rabbitmq_relation_changed(self, _: HookEvent) -> None:
        """Handle RabbitMQ changed."""
        if self.rabbitmq_parameters():
            self.on.ready.emit()

    def _on_rabbitmq_relation_broken(self, _: HookEvent) -> None:
        """Handle RabbitMQ broken."""
        self.on.goneaway.emit()

    @property
    def _rabbitmq_rel(self) -> Relation | None:
        """The RabbitMQ relation."""
        return self.framework.model.get_relation(self.relation_name)

    def rabbitmq_parameters(self) -> RabbitMQParameters | None:
        """Return RabbitMQ parameters with the data in the relation.

        It will try to use the format in rabbitmq-k8s or rabbitmq-server.
        If there is no relation or the data is not complete, it returns None.

        Returns:
            The parameters for RabbitMQ or None.
        """
        rabbitmq_k8s_params = self._rabbitmq_k8s_parameters()
        if rabbitmq_k8s_params:
            return rabbitmq_k8s_params

        # rabbitmq-server parameters or None.
        return self._rabbitmq_server_parameters()

    def request_access(self, username: str, vhost: str) -> None:
        """Request access to the RabbitMQ server.

        Args:
           username: username requested for RabbitMQ
           vhost: virtual host requested for RabbitMQ
        """
        if self.model.unit.is_leader():
            if self._rabbitmq_rel:
                self._rabbitmq_rel.data[self.charm.app]["username"] = username
                self._rabbitmq_rel.data[self.charm.app]["vhost"] = vhost
            else:
                logger.warning("request_access but no rabbitmq relation")

    def _rabbitmq_server_parameters(self) -> RabbitMQParameters | None:
        """Return parameters for rabbitmq-server.

        Returns:
            Returns parameters for rabbitmq-server or None if they are not valid/complete.
        """
        if not self._rabbitmq_rel:
            return None

        password = None
        hostnames = []
        for unit in self._rabbitmq_rel.units:
            unit_data = self._rabbitmq_rel.data[unit]
            # All of the passwords should be equal. If it is
            # in the unit data, get it and override the password
            password = unit_data.get("password", password)
            unit_hostname = unit_data.get("hostname")
            if unit_hostname:
                hostnames.append(unit_hostname)

        if not password or len(hostnames) == 0:
            return None

        hostname = hostnames[0]
        return RabbitMQParameters(
            hostname=hostname,
            hostnames=hostnames,
            username=self.username,
            password=password,
            vhost=self.vhost,
        )

    def _rabbitmq_k8s_parameters(self) -> RabbitMQParameters | None:
        """Return parameters for rabbitmq-k8s.

        Returns:
            Returns parameters for rabbitmq-k8s or None if they are not valid/complete.
        """
        if not self._rabbitmq_rel:
            return None

        # A password in the _rabbitmq_rel data differentiates rabbitmq-k8s from rabbitmq-server
        password = self._rabbitmq_rel.data[self._rabbitmq_rel.app].get("password")
        hostname = self._rabbitmq_rel.data[self._rabbitmq_rel.app].get("hostname")

        hostnames = []
        for unit in self._rabbitmq_rel.units:
            unit_data = self._rabbitmq_rel.data[unit]
            ingress_address = unit_data.get("ingress-address")
            if ingress_address:
                hostnames.append(ingress_address)

        if not password or not hostname:
            return None

        return RabbitMQParameters(
            hostname=hostname,
            hostnames=hostnames,
            username=self.username,
            password=password,
            vhost=self.vhost,
        )
