# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The base Gunicorn charm class for all WSGI application charms."""
import abc
import logging

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequiresEvent
from charms.redis_k8s.v0.redis import RedisRelationCharmEvents, RedisRequires
from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer
from pydantic import BaseModel  # pylint: disable=no-name-in-module

from paas_app_charmer._gunicorn.charm_state import CharmState
from paas_app_charmer._gunicorn.charm_utils import block_if_invalid_config
from paas_app_charmer._gunicorn.observability import Observability
from paas_app_charmer._gunicorn.secret_storage import GunicornSecretStorage
from paas_app_charmer._gunicorn.webserver import GunicornWebserver, WebserverConfig
from paas_app_charmer._gunicorn.workload_config import WorkloadConfig
from paas_app_charmer._gunicorn.wsgi_app import WsgiApp
from paas_app_charmer.database_migration import DatabaseMigration, DatabaseMigrationStatus
from paas_app_charmer.databases import make_database_requirers
from paas_app_charmer.exceptions import CharmConfigInvalidError

logger = logging.getLogger(__name__)


class GunicornBase(abc.ABC, ops.CharmBase):  # pylint: disable=too-many-instance-attributes
    """Gunicorn-based charm service mixin.

    Attrs:
        on: charm events replaced by Redis ones for the Redis charm library.
    """

    @abc.abstractmethod
    def get_wsgi_config(self) -> BaseModel:
        """Return the framework related configurations."""

    @abc.abstractmethod
    def get_cos_dir(self) -> str:
        """Return the directory with COS related files."""

    on = RedisRelationCharmEvents()

    def __init__(self, framework: ops.Framework, wsgi_framework: str) -> None:
        """Initialize the instance.

        Args:
            framework: operator framework.
            wsgi_framework: WSGI framework name.
        """
        super().__init__(framework)
        self._wsgi_framework = wsgi_framework

        self._secret_storage = GunicornSecretStorage(
            charm=self, key=f"{wsgi_framework}_secret_key"
        )
        self._database_requirers = make_database_requirers(self, self.app.name)

        requires = self.framework.meta.requires
        if "redis" in requires and requires["redis"].interface_name == "redis":
            self._redis = RedisRequires(charm=self, relation_name="redis")
            self.framework.observe(self.on.redis_relation_updated, self._on_redis_relation_updated)
        else:
            self._redis = None

        self._workload_config = WorkloadConfig(self._wsgi_framework)

        self._database_migration = DatabaseMigration(
            container=self.unit.get_container(self._workload_config.container_name),
            state_dir=self._workload_config.state_dir,
        )

        self._webserver_config = WebserverConfig.from_charm(self)

        self._container = self.unit.get_container(f"{self._workload_config.framework}-app")

        self._ingress = IngressPerAppRequirer(
            self,
            port=self._workload_config.port,
            strip_prefix=True,
        )

        self._observability = Observability(
            self,
            log_files=self._workload_config.log_files,
            container_name=self._workload_config.container_name,
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
        """Configure the application pebble service layer.

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
            event.fail("charm is still initializing")
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
        charm_state = self._build_charm_state()

        if not self._container.can_connect():
            logger.info(
                "pebble client in the %s container is not ready", self._workload_config.framework
            )
            self._update_app_and_unit_status(ops.WaitingStatus("Waiting for pebble ready"))
            return False
        if not charm_state.is_secret_storage_ready:
            logger.info("secret storage is not initialized")
            self._update_app_and_unit_status(ops.WaitingStatus("Waiting for peer integration"))
            return False
        return True

    def restart(self) -> None:
        """Restart or start the service if not started with the latest configuration."""
        if not self.is_ready():
            return
        try:
            self._update_app_and_unit_status(
                ops.MaintenanceStatus("Preparing service for restart")
            )
            self._build_wsgi_app().restart()
        except CharmConfigInvalidError as exc:
            self._update_app_and_unit_status(ops.BlockedStatus(exc.msg))
            return
        self._update_app_and_unit_status(ops.ActiveStatus())

    def _gen_environment(self) -> dict[str, str]:
        """Generate the environment dictionary used for the App.

        This method is useful to generate the environment variables to
        run actions against the workload container for subclasses.

        Returns:
            A dictionary representing the application environment variables.
        """
        return self._build_wsgi_app().gen_environment()

    def _build_charm_state(self) -> CharmState:
        """Build charm state.

        Returns:
            New CharmState
        """
        return CharmState.from_charm(
            charm=self,
            framework=self._wsgi_framework,
            wsgi_config=self.get_wsgi_config(),
            secret_storage=self._secret_storage,
            database_requirers=self._database_requirers,
            redis_uri=self._redis.url if self._redis is not None else None,
        )

    def _build_wsgi_app(self) -> WsgiApp:
        """Build a WsgiApp instance.

        Returns:
            A new WsgiApp instance.
        """
        charm_state = self._build_charm_state()

        webserver = GunicornWebserver(
            webserver_config=self._webserver_config,
            workload_config=self._workload_config,
            container=self.unit.get_container(self._workload_config.container_name),
        )

        return WsgiApp(
            container=self._container,
            charm_state=charm_state,
            workload_config=self._workload_config,
            webserver=webserver,
            database_migration=self._database_migration,
        )

    @block_if_invalid_config
    def _on_update_status(self, _: ops.HookEvent) -> None:
        """Handle the update-status event."""
        if self._database_migration.get_status() == DatabaseMigrationStatus.FAILED:
            self.restart()

    @block_if_invalid_config
    def _on_mysql_database_database_created(self, _event: DatabaseRequiresEvent) -> None:
        """Handle mysql's database-created event."""
        self.restart()

    @block_if_invalid_config
    def _on_mysql_database_endpoints_changed(self, _event: DatabaseRequiresEvent) -> None:
        """Handle mysql's endpoints-changed event."""
        self.restart()

    @block_if_invalid_config
    def _on_mysql_database_relation_broken(self, _event: ops.RelationBrokenEvent) -> None:
        """Handle mysql's relation-broken event."""
        self.restart()

    @block_if_invalid_config
    def _on_postgresql_database_database_created(self, _event: DatabaseRequiresEvent) -> None:
        """Handle postgresql's database-created event."""
        self.restart()

    @block_if_invalid_config
    def _on_postgresql_database_endpoints_changed(self, _event: DatabaseRequiresEvent) -> None:
        """Handle mysql's endpoints-changed event."""
        self.restart()

    @block_if_invalid_config
    def _on_postgresql_database_relation_broken(self, _event: ops.RelationBrokenEvent) -> None:
        """Handle postgresql's relation-broken event."""
        self.restart()

    @block_if_invalid_config
    def _on_mongodb_database_database_created(self, _event: DatabaseRequiresEvent) -> None:
        """Handle mongodb's database-created event."""
        self.restart()

    @block_if_invalid_config
    def _on_mongodb_database_endpoints_changed(self, _event: DatabaseRequiresEvent) -> None:
        """Handle mysql's endpoints-changed event."""
        self.restart()

    @block_if_invalid_config
    def _on_mongodb_database_relation_broken(self, _event: ops.RelationBrokenEvent) -> None:
        """Handle postgresql's relation-broken event."""
        self.restart()

    @block_if_invalid_config
    def _on_redis_relation_updated(self, _event: DatabaseRequiresEvent) -> None:
        """Handle redis's database-created event."""
        self.restart()
