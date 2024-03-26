#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The base Gunicorn charm class for all WSGI application charms."""
import abc
import logging

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequiresEvent
from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer
from pydantic import BaseModel  # pylint: disable=no-name-in-module

from paas_app_charmer._gunicorn.charm_state import CharmState
from paas_app_charmer._gunicorn.observability import Observability
from paas_app_charmer._gunicorn.secret_storage import GunicornSecretStorage
from paas_app_charmer._gunicorn.webserver import GunicornWebserver
from paas_app_charmer._gunicorn.wsgi_app import WsgiApp
from paas_app_charmer.database_migration import DatabaseMigration, DatabaseMigrationStatus
from paas_app_charmer.databases import Databases, make_database_requirers
from paas_app_charmer.exceptions import CharmConfigInvalidError

logger = logging.getLogger(__name__)


class GunicornBase(abc.ABC, ops.CharmBase):  # pylint: disable=too-many-instance-attributes
    """Gunicorn-based charm service mixin."""

    @abc.abstractmethod
    def get_wsgi_config(self) -> BaseModel:
        """Return the framework related configurations."""

    @abc.abstractmethod
    def get_cos_dir(self) -> str:
        """Return the directory with COS related files."""

    def __init__(self, framework: ops.Framework, wsgi_framework: str) -> None:
        """Initialize the instance.

        Args:
            framework: operator framework.
            wsgi_framework: WSGI framework name.
        """
        super().__init__(framework)
        self._secret_storage = GunicornSecretStorage(
            charm=self, key=f"{wsgi_framework}_secret_key"
        )
        self._database_requirers = make_database_requirers(self, self.app.name)
        try:
            wsgi_config = self.get_wsgi_config()
        except CharmConfigInvalidError as exc:
            self._update_app_and_unit_status(ops.BlockedStatus(exc.msg))
            return

        self._charm_state = CharmState.from_charm(
            charm=self,
            framework=wsgi_framework,
            wsgi_config=wsgi_config,
            secret_storage=self._secret_storage,
            database_requirers=self._database_requirers,
        )
        self._database_migration = DatabaseMigration(
            container=self.unit.get_container(self._charm_state.container_name),
            state_dir=self._charm_state.state_dir,
        )
        webserver = GunicornWebserver(
            charm_state=self._charm_state,
            container=self.unit.get_container(self._charm_state.container_name),
        )
        self._container = self.unit.get_container(f"{self._charm_state.framework}-app")
        self._wsgi_app = WsgiApp(
            container=self._container,
            charm_state=self._charm_state,
            webserver=webserver,
            database_migration=self._database_migration,
        )
        self._databases = Databases(
            charm=self,
            application=self._wsgi_app,
            database_requirers=self._database_requirers,
        )
        self._ingress = IngressPerAppRequirer(
            self,
            port=self._charm_state.port,
            strip_prefix=True,
        )
        self._observability = Observability(
            self,
            charm_state=self._charm_state,
            container_name=self._charm_state.container_name,
            cos_dir=self.get_cos_dir(),
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.rotate_secret_key_action, self._on_rotate_secret_key_action)
        self.framework.observe(
            self.on.secret_storage_relation_changed,
            self._on_secret_storage_relation_changed,
        )
        self.framework.observe(self.on.update_status, self._on_update_status)
        for database, database_requirer in self._database_requirers.items():
            self.framework.observe(
                database_requirer.on.database_created,
                getattr(self, f"_on_{database}_database_database_created"),
            )
            self.framework.observe(
                database_requirer.on.endpoints_changed,
                getattr(self, f"_on_{database}_database_endpoints_changed"),
            )
            self.framework.observe(
                self.on[database_requirer.relation_name].relation_broken,
                getattr(self, f"_on_{database}_database_relation_broken"),
            )

    def _on_config_changed(self, _event: ops.EventBase) -> None:
        """Configure the flask pebble service layer.

        Args:
            _event: the config-changed event that triggers this callback function.
        """
        self.restart()

    def _on_rotate_secret_key_action(self, event: ops.ActionEvent) -> None:
        """Handle the rotate-secret-key action.

        Args:
            event: the action event that trigger this callback.
        """
        if not self.unit.is_leader():
            event.fail("only leader unit can rotate secret key")
            return
        if not self._secret_storage.is_initialized:
            event.fail("flask charm is still initializing")
            return
        self._secret_storage.reset_secret_key()
        event.set_results({"status": "success"})
        self.restart()

    def _on_secret_storage_relation_changed(self, _event: ops.RelationEvent) -> None:
        """Handle the secret-storage-relation-changed event.

        Args:
            _event: the action event that triggers this callback.
        """
        self.restart()

    def _update_app_and_unit_status(self, status: ops.StatusBase) -> None:
        """Update the application and unit status.

        Args:
            status: the desired application and unit status.
        """
        self.unit.status = status
        if self.unit.is_leader():
            self.app.status = status

    def is_ready(self) -> bool:
        """Check if the charm is ready to start the workload application.

        Returns:
            True if the charm is ready to start the workload application.
        """
        if not self._container.can_connect():
            logger.info(
                "pebble client in the %s container is not ready", self._charm_state.framework
            )
            self._update_app_and_unit_status(ops.WaitingStatus("Waiting for pebble ready"))
            return False
        if not self._charm_state.is_secret_storage_ready:
            logger.info("secret storage is not initialized")
            self._update_app_and_unit_status(ops.WaitingStatus("Waiting for peer integration"))
            return False
        return True

    def restart(self) -> None:
        """Restart or start the flask service if not started with the latest configuration."""
        if not self.is_ready():
            return
        try:
            self._wsgi_app.restart()
        except CharmConfigInvalidError as exc:
            self._update_app_and_unit_status(ops.BlockedStatus(exc.msg))
            return
        self._update_app_and_unit_status(ops.ActiveStatus())

    def _on_update_status(self, _: ops.HookEvent) -> None:
        """Handle the update-status event."""
        if self._database_migration.get_status() == DatabaseMigrationStatus.FAILED:
            self.restart()

    def _on_mysql_database_database_created(self, _event: DatabaseRequiresEvent) -> None:
        """Handle the mysql's database-created event."""
        self.restart()

    def _on_mysql_database_endpoints_changed(self, _event: DatabaseRequiresEvent) -> None:
        """Handle the mysql's endpoints-changed event."""
        self.restart()

    def _on_mysql_database_relation_broken(self, _event: ops.RelationBrokenEvent) -> None:
        """Handle the mysql's relation-broken event."""
        self.restart()

    def _on_postgresql_database_database_created(self, _event: DatabaseRequiresEvent) -> None:
        """Handle the postgresql's database-created event."""
        self.restart()

    def _on_postgresql_database_endpoints_changed(self, _event: DatabaseRequiresEvent) -> None:
        """Handle the mysql's endpoints-changed event."""
        self.restart()

    def _on_postgresql_database_relation_broken(self, _event: ops.RelationBrokenEvent) -> None:
        """Handle the postgresql's relation-broken event."""
        self.restart()

    def _on_mongodb_database_database_created(self, _event: DatabaseRequiresEvent) -> None:
        """Handle the mongodb's database-created event."""
        self.restart()

    def _on_mongodb_database_endpoints_changed(self, _event: DatabaseRequiresEvent) -> None:
        """Handle the mysql's endpoints-changed event."""
        self.restart()

    def _on_mongodb_database_relation_broken(self, _event: ops.RelationBrokenEvent) -> None:
        """Handle the postgresql's relation-broken event."""
        self.restart()

    def _on_redis_database_database_created(self, _event: DatabaseRequiresEvent) -> None:
        """Handle the redis's database-created event."""
        self.restart()

    def _on_redis_database_endpoints_changed(self, _event: DatabaseRequiresEvent) -> None:
        """Handle the mysql's endpoints-changed event."""
        self.restart()

    def _on_redis_database_relation_broken(self, _event: ops.RelationBrokenEvent) -> None:
        """Handle the postgresql's relation-broken event."""
        self.restart()
