# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The base charm class for all application charms."""
import abc
import logging

import ops
from charms.redis_k8s.v0.redis import RedisRelationCharmEvents
from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer
from ops.model import Container
from pydantic import BaseModel, ValidationError

from paas_app_charmer.app import App, WorkloadConfig
from paas_app_charmer.charm_integrations import Integrations
from paas_app_charmer.charm_state import CharmState
from paas_app_charmer.charm_utils import block_if_invalid_config
from paas_app_charmer.database_migration import DatabaseMigration, DatabaseMigrationStatus
from paas_app_charmer.exceptions import CharmConfigInvalidError
from paas_app_charmer.observability import Observability
from paas_app_charmer.secret_storage import KeySecretStorage
from paas_app_charmer.utils import build_validation_error_message

logger = logging.getLogger(__name__)


class PaasCharm(abc.ABC, ops.CharmBase):  # pylint: disable=too-many-instance-attributes
    """PaasCharm base charm service mixin.

    Attrs:
        on: charm events replaced by Redis ones for the Redis charm library.
        framework_config_class: base class for the framework config.
    """

    framework_config_class: type[BaseModel]

    @abc.abstractmethod
    def get_cos_dir(self) -> str:
        """Return the directory with COS related files."""

    @property
    @abc.abstractmethod
    def _workload_config(self) -> WorkloadConfig:
        """Return an WorkloadConfig instance."""

    @abc.abstractmethod
    def _create_app(self) -> App:
        """Create an App instance."""

    on = RedisRelationCharmEvents()

    def __init__(self, framework: ops.Framework, framework_name: str) -> None:
        """Initialize the instance.

        Args:
            framework: operator framework.
            framework_name: framework name.
        """
        super().__init__(framework)
        self._framework_name = framework_name

        self._secret_storage = KeySecretStorage(charm=self, key=f"{framework_name}_secret_key")

        self.charm_integrations = Integrations(self)
        self.charm_integrations.register(self._on_generic_integration_event)

        self._database_migration = DatabaseMigration(
            container=self.unit.get_container(self._workload_config.container_name),
            state_dir=self._workload_config.state_dir,
        )

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
            metrics_target=self._workload_config.metrics_target,
            metrics_path=self._workload_config.metrics_path,
        )

        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.rotate_secret_key_action, self._on_rotate_secret_key_action)
        self.framework.observe(
            self.on.secret_storage_relation_changed,
            self._on_secret_storage_relation_changed,
        )
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self._ingress.on.ready, self._on_ingress_ready)
        self.framework.observe(self._ingress.on.revoked, self._on_ingress_revoked)
        self.framework.observe(
            self.on[self._workload_config.container_name].pebble_ready, self._on_pebble_ready
        )

    def get_framework_config(self) -> BaseModel:
        """Return the framework related configurations.

        Raises:
            CharmConfigInvalidError: if charm config is not valid.

        Returns:
             Framework related configurations.
        """
        # Will raise an AttributeError if it the attribute framework_config_class does not exist.
        framework_config_class = self.framework_config_class
        config = dict(self.config.items())
        try:
            return framework_config_class.model_validate(config)
        except ValidationError as exc:
            error_message = build_validation_error_message(exc, underscore_to_dash=False)
            raise CharmConfigInvalidError(f"invalid configuration: {error_message}") from exc

    @property
    def _container(self) -> Container:
        """Return the workload container."""
        return self.unit.get_container(self._workload_config.container_name)

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
        charm_state = self._create_charm_state()

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

        missing_integrations = self.charm_integrations.missing_integrations()
        if missing_integrations:
            self._create_app().stop_all_services()
            self._database_migration.set_status_to_pending()
            message = f"missing integrations: {', '.join(missing_integrations)}"
            logger.info(message)
            self.update_app_and_unit_status(ops.BlockedStatus(message))
            return False

        return True

    def restart(self) -> None:
        """Restart or start the service if not started with the latest configuration."""
        if not self.is_ready():
            return
        try:
            self.update_app_and_unit_status(ops.MaintenanceStatus("Preparing service for restart"))
            self._create_app().restart()
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
        return self._create_app().gen_environment()

    def _create_charm_state(self) -> CharmState:
        """Create charm state.

        This method may raise CharmConfigInvalidError.

        Returns:
            New CharmState
        """
        return CharmState.from_charm(
            charm=self,
            framework=self._framework_name,
            framework_config=self.get_framework_config(),
            secret_storage=self._secret_storage,
            integrations=self.charm_integrations.create_integrations_state(),
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

    @block_if_invalid_config
    def _on_update_status(self, _: ops.HookEvent) -> None:
        """Handle the update-status event."""
        if self._database_migration.get_status() == DatabaseMigrationStatus.FAILED:
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

    @block_if_invalid_config
    def _on_pebble_ready(self, _: ops.PebbleReadyEvent) -> None:
        """Handle the pebble-ready event."""
        self.restart()

    @block_if_invalid_config
    def _on_generic_integration_event(self, _event: ops.HookEvent) -> None:
        """Handle generic integration event."""
        self.restart()
