# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Go Charm service."""

import pathlib
import typing

import ops
from pydantic import BaseModel, Extra, Field, ValidationError

from paas_app_charmer._generic.generic_app import GenericApp
from paas_app_charmer.app import App, AppConfig
from paas_app_charmer.charm import PaasCharm
from paas_app_charmer.exceptions import CharmConfigInvalidError
from paas_app_charmer.utils import build_validation_error_message


class GoConfig(BaseModel, extra=Extra.allow):
    """Represent Go builtin configuration values.

    Attrs:
        port: port where the application is listening
        metrics_port: port where the metrics are collected
        metrics_path: path where the metrics are collected
        secret_key: a secret key that will be used for securely signing the session cookie
            and can be used for any other security related needs by your Flask application.
    """

    port: int = Field(default=8080, gt=0)
    metrics_port: int | None = Field(default=8080, gt=0)
    metrics_path: str | None = Field(default=None, min_length=1)
    secret_key: str | None = Field(default=None, min_length=1)


class Charm(PaasCharm):  # pylint: disable=too-many-instance-attributes
    """Go Charm service."""

    def __init__(self, framework: ops.Framework) -> None:
        """Initialize the Go charm.

        Args:
            framework: operator framework.
        """
        super().__init__(framework=framework, framework_name="go")

    @property
    def _app_config(self) -> AppConfig:
        """Return an AppConfig instance."""
        framework_name = self._framework_name
        base_dir = pathlib.Path("/app")
        framework_config = typing.cast(GoConfig, self.get_framework_config())
        return AppConfig(
            framework=framework_name,
            container_name="app",
            port=framework_config.port,
            base_dir=base_dir,
            app_dir=base_dir,
            state_dir=base_dir / "state",
            service_name=framework_name,
            log_files=[],
            # JAVI review the / between port and path.
            metric_targets=[f"*:{framework_config.metrics_port}{framework_config.metrics_path}"],
        )

    def get_framework_config(self) -> BaseModel:
        """Return Go framework related configurations.

        Returns:
             Go framework related configurations.

        Raises:
            CharmConfigInvalidError: if charm config is not valid.
        """
        # JAVI NO PREFIX IN THIS CONFIG, DIFFERENT FROM FLASK AND DJANGO
        config = {k.replace("-", "_"): v for k, v in self.config.items()}
        try:
            return GoConfig.model_validate(config)
        except ValidationError as exc:
            error_message = build_validation_error_message(exc, underscore_to_dash=True)
            raise CharmConfigInvalidError(f"invalid configuration: {error_message}") from exc

    def get_cos_dir(self) -> str:
        """Return the directory with COS related files.

        Returns:
            Return the directory with COS related files.
        """
        return str((pathlib.Path(__file__).parent / "cos").absolute())

    def _create_app(self) -> App:
        """Build a App instance.

        Returns:
            A new App instance.
        """
        charm_state = self._create_charm_state()
        return GenericApp(
            container=self._container,
            charm_state=charm_state,
            app_config=self._app_config,
            database_migration=self._database_migration,
        )
