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

# rabbitmq-k8s
# unit-flask-k8s-0: 15:27:43 INFO unit.flask-k8s/0.juju-log JAVI rabbitmq_requires._amqp_rel.data {<ops.model.Unit flask-k8s/0>: {'egress-subnets': '10.152.183.168/32', 'ingress-address': '10.152.183.168', 'private-address': '10.152.183.168'}, <ops.model.Application flask-k8s>: {'username': 'flask-k8s', 'vhost': '/'}, <ops.model.Unit rabbitmq-k8s/0>: {'egress-subnets': '10.12.97.225/32', 'ingress-address': '10.12.97.225', 'private-address': '10.12.97.225'}, <ops.model.Unit rabbitmq-k8s/1>: {'egress-subnets': '10.12.97.225/32', 'ingress-address': '10.12.97.225', 'private-address': '10.12.97.225'}, <ops.model.Application rabbitmq-k8s>: {'hostname': 'rabbitmq-k8s-endpoints.testing.svc.cluster.local', 'password': '3m036hhyiDHs'}} # noqa: W505 # pylint: disable=line-too-long

# rabbitmq-server
# unit-flask-k8s-0: 16:00:16 INFO unit.flask-k8s/0.juju-log amqp:3: JAVI rabbitmq_requires._amqp_rel.data {<ops.model.Unit flask-k8s/0>: {'egress-subnets': '10.152.183.168/32', 'ingress-address': '10.152.183.168', 'private-address': '10.152.183.168'}, <ops.model.Application flask-k8s>: {'username': 'flask-k8s', 'vhost': '/'}, <ops.model.Unit rabbitmq-server/2>: {'hostname': '10.58.171.158', 'password': 'LGg6HMJXPF8G3cHMcMg28ZpwSWRfS6hb8s57Jfkt5TW3rtgV5ypZkV8ZY4GcrhW8', 'private-address': '10.58.171.158'}, <ops.model.Unit rabbitmq-server/1>: {'hostname': '10.58.171.70', 'password': 'LGg6HMJXPF8G3cHMcMg28ZpwSWRfS6hb8s57Jfkt5TW3rtgV5ypZkV8ZY4GcrhW8', 'private-address': '10.58.171.70'}, <ops.model.Unit rabbitmq-server/0>: {'egress-subnets': '10.58.171.146/32', 'hostname': '10.58.171.146', 'ingress-address': '10.58.171.146', 'password': 'LGg6HMJXPF8G3cHMcMg28ZpwSWRfS6hb8s57Jfkt5TW3rtgV5ypZkV8ZY4GcrhW8', 'private-address': '10.58.171.146'}, <ops.model.Application rabbitmq-server>: {}}
"""


# JAVI COPYPASTED FOR NOW!
# JAVI EXPLAIN NO SSL CLIENT CERFICATES YET
import logging
from typing import cast

from ops import CharmBase, HookEvent
from ops.framework import EventBase, EventSource, Object, ObjectEvents
from ops.model import Relation
from pydantic import ValidationError

from paas_app_charmer.charm_state import RabbitMQParameters
from paas_app_charmer.utils import build_validation_error_message

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
        connected: JAVI TODO
        ready: JAVI TODO
        goneaway: JAVI TODO
    """

    connected = EventSource(RabbitMQConnectedEvent)
    ready = EventSource(RabbitMQReadyEvent)
    goneaway = EventSource(RabbitMQGoneAwayEvent)


class RabbitMQRequires(Object):
    """RabbitMQRequires class.

    Attributes:
        on: JAVI TODO
    """

    on = RabbitMQServerEvents()

    def __init__(self, charm: CharmBase, relation_name: str, username: str, vhost: str):
        """JAVI TODO.

        Args:
           charm: JAVI TODO
           relation_name: JAVI TODO
           username: JAVI TODO
           vhost: JAVI TODO
        """
        super().__init__(charm, relation_name)
        self.charm = charm
        self.relation_name = relation_name
        self.username = username
        self.vhost = vhost
        self.framework.observe(
            self.charm.on[relation_name].relation_joined,
            self._on_amqp_relation_joined,
        )
        self.framework.observe(
            self.charm.on[relation_name].relation_changed,
            self._on_amqp_relation_changed,
        )
        self.framework.observe(
            self.charm.on[relation_name].relation_departed,
            self._on_amqp_relation_changed,
        )
        self.framework.observe(
            self.charm.on[relation_name].relation_broken,
            self._on_amqp_relation_broken,
        )

    def _on_amqp_relation_joined(self, _: HookEvent) -> None:
        """JAVI TODO."""
        logging.debug("RabbitMQRabbitMQRequires on_joined")
        self.on.connected.emit()
        self.request_access(self.username, self.vhost)

    def _on_amqp_relation_changed(self, _: HookEvent) -> None:
        """JAVI TODO."""
        logging.debug("RabbitMQRabbitMQRequires on_changed/departed")
        if self.rabbitmq_parameters():
            self.on.ready.emit()

    def _on_amqp_relation_broken(self, _: HookEvent) -> None:
        """JAVI TODO."""
        logging.debug("RabbitMQRabbitMQRequires on_broken")
        self.on.goneaway.emit()

    @property
    def _amqp_rel(self) -> Relation | None:
        """The RabbitMQ relation."""
        return self.framework.model.get_relation(self.relation_name)

    def rabbitmq_parameters(self) -> RabbitMQParameters | None:
        """TODO JAVI.

        Returns:
            TODO JAVI
        """
        if self._amqp_rel:
            # just put everything.
            hostnames = []
            password = None
            for unit in self._amqp_rel.units:
                unit_data = self._amqp_rel.data[unit]
                ingress_address = unit_data.get("ingress-address")
                unit_hostname = unit_data.get("hostname", ingress_address)
                if unit_hostname:
                    hostnames.append(unit_hostname)
                # all of them should be equal
                password = unit_data.get("password", password)

            password = self._amqp_rel.data[self._amqp_rel.app].get("password", password)
            first_hostname = hostnames[0] if len(hostnames) > 0 else None
            hostname = self._amqp_rel.data[self._amqp_rel.app].get("hostname", first_hostname)

            try:
                return RabbitMQParameters(
                    hostname=cast(str, hostname),
                    hostnames=hostnames,
                    username=self.username,
                    password=cast(str, password),
                    vhost=self.vhost,
                )
            except ValidationError as exc:
                # do not crash, as the relation can be starting at this moment, and the
                # data not being there in the current hook
                error_message = build_validation_error_message(exc)
                logger.info("Error validating RabbitMQ parameters %s", error_message)
                return None
        return None

    def request_access(self, username: str, vhost: str) -> None:
        """Request access to the RabbitMQ server.

        Args:
           username: JAVI TODO
           vhost: JAVI TODO
        """
        if self.model.unit.is_leader():
            logging.debug("Requesting RabbitMQ user and vhost")
            if self._amqp_rel:
                self._amqp_rel.data[self.charm.app]["username"] = username
                self._amqp_rel.data[self.charm.app]["vhost"] = vhost
            else:
                logger.warning("request_access but no rabbitmq relation")
