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

# Until charmcraft fetch-libs is implemented, the charm will not fail
# if new optional libs are not fetched, as it will not be backwards compatible.
try:
    # pylint: disable=ungrouped-imports
    from charms.data_platform_libs.v0.s3 import S3Requirer
except ImportError:
    logger.exception(
        "Missing charm library, please run `charmcraft fetch-lib charms.data_platform_libs.v0.s3`"
    )

try:
    # pylint: disable=ungrouped-imports
    from charms.saml_integrator.v0.saml import SamlRequires
except ImportError:
    logger.exception(
        "Missing charm library, please run `charmcraft fetch-lib charms.saml_integrator.v0.saml`"
    )


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

        if "s3" in requires and requires["s3"].interface_name == "s3":
            self._s3 = S3Requirer(charm=self, relation_name="s3", bucket_name=self.app.name)
            self.framework.observe(self._s3.on.credentials_changed, self._on_s3_credential_changed)
            self.framework.observe(self._s3.on.credentials_gone, self._on_s3_credential_gone)
        else:
            self._s3 = None

        if "saml" in requires and requires["saml"].interface_name == "saml":
            self._saml = SamlRequires(self)
            self.framework.observe(self._saml.on.saml_data_available, self._on_saml_data_available)
        else:
            self._saml = None

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
        self.framework.observe(self._ingress.on.ready, self._on_ingress_ready)
        self.framework.observe(self._ingress.on.revoked, self._on_ingress_revoked)

    @block_if_invalid_config
    def _on_config_changed(self, _event: ops.EventBase) -> None:
        """Configure the application pebble service layer.

        Args:
            _event: the config-changed event that triggers this callback function.
        """
        self.restart()

    @block_if_invalid_config
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

    @block_if_invalid_config
    def _on_secret_storage_relation_changed(self, _event: ops.RelationEvent) -> None:
        """Handle the secret-storage-relation-changed event.

        Args:
            _event: the action event that triggers this callback.
        """
        self.restart()

    def update_app_and_unit_status(self, status: ops.StatusBase) -> None:
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
            self.update_app_and_unit_status(ops.WaitingStatus("Waiting for pebble ready"))
            return False
        if not charm_state.is_secret_storage_ready:
            logger.info("secret storage is not initialized")
            self.update_app_and_unit_status(ops.WaitingStatus("Waiting for peer integration"))
            return False

        missing_integrations = self._missing_required_integrations(charm_state)
        if missing_integrations:
            self._build_wsgi_app().stop_all_services()
            self._database_migration.set_status_to_pending()
            message = f"missing integrations: {', '.join(missing_integrations)}"
            logger.info(message)
            self.update_app_and_unit_status(ops.BlockedStatus(message))
            return False

        return True

    def _missing_required_integrations(self, charm_state: CharmState) -> list[str]:
        """Get list of missing integrations that are required.

        Args:
            charm_state: the charm state

        Returns:
            list of names of missing integrations
        """
        missing_integrations = []
        requires = self.framework.meta.requires
        for name in self._database_requirers.keys():
            if (
                name not in charm_state.integrations.databases_uris
                or charm_state.integrations.databases_uris[name] is None
            ):
                if not requires[name].optional:
                    missing_integrations.append(name)
        if self._redis and not charm_state.integrations.redis_uri:
            if not requires["redis"].optional:
                missing_integrations.append("redis")
        if self._s3 and not charm_state.integrations.s3_parameters:
            if not requires["s3"].optional:
                missing_integrations.append("s3")
        if self._saml and not charm_state.integrations.saml_parameters:
            if not requires["saml"].optional:
                missing_integrations.append("saml")
        return missing_integrations

    def restart(self) -> None:
        """Restart or start the service if not started with the latest configuration."""
        if not self.is_ready():
            return
        try:
            self.update_app_and_unit_status(ops.MaintenanceStatus("Preparing service for restart"))
            self._build_wsgi_app().restart()
        except CharmConfigInvalidError as exc:
            self.update_app_and_unit_status(ops.BlockedStatus(exc.msg))
            return
        self.unit.open_port("tcp", self._workload_config.port)
        self.update_app_and_unit_status(ops.ActiveStatus())

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

        This method may raise CharmConfigInvalidError.

        Returns:
            New CharmState
        """
        if self._saml:
            saml_relation = self.model.get_relation(self._saml.relation_name)
            if saml_relation and saml_relation.app in saml_relation.data:
                saml_relation_data = saml_relation.data[saml_relation.app]
            else:
                saml_relation_data = None
        else:
            saml_relation_data = None

        return CharmState.from_charm(
            charm=self,
            framework=self._wsgi_framework,
            wsgi_config=self.get_wsgi_config(),
            secret_storage=self._secret_storage,
            database_requirers=self._database_requirers,
            redis_uri=self._redis.url if self._redis is not None else None,
            s3_connection_info=self._s3.get_s3_connection_info() if self._s3 else None,
            saml_relation_data=saml_relation_data,
            base_url=self._base_url,
        )

    @property
    def _base_url(self) -> str:
        """Return the base_url for the service.

        This URL will be the ingress URL if there is one, otherwise it will
        point to the K8S service.
        """
        if self._ingress.url:
            return self._ingress.url
        return f"http://{self.app.name}.{self.model.name}:{self._workload_config.port}"

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

    @block_if_invalid_config
    def _on_s3_credential_changed(self, _event: ops.HookEvent) -> None:
        """Handle s3 credentials-changed event."""
        self.restart()

    @block_if_invalid_config
    def _on_s3_credential_gone(self, _event: ops.HookEvent) -> None:
        """Handle s3 credentials-gone event."""
        self.restart()

    @block_if_invalid_config
    def _on_saml_data_available(self, _event: ops.HookEvent) -> None:
        """Handle saml data available event."""
        self.restart()

    @block_if_invalid_config
    def _on_ingress_revoked(self, _: ops.HookEvent) -> None:
        """Handle event for ingress revoked."""
        self.restart()

    @block_if_invalid_config
    def _on_ingress_ready(self, _: ops.HookEvent) -> None:
        """Handle event for ingress ready."""
        self.restart()
