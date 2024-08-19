# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""FastAPI Charm service."""

import pathlib
import typing

import ops
from pydantic import BaseModel, Extra, Field

from paas_app_charmer.app import App, WorkloadConfig
from paas_app_charmer.charm import PaasCharm


class FastAPIConfig(BaseModel, extra=Extra.allow):
    """Represent FastAPI builtin configuration values.

    Attrs:
        uvicorn_port: port where the application is listening
        web_concurrency: number of workers for uvicorn
        uvicorn_log_level: uvicorn log level
        metrics_port: port where the metrics are collected
        metrics_path: path where the metrics are collected
        secret_key: a secret key that will be used for securely signing the session cookie
            and can be used for any other security related needs by your Flask application.
    """

    uvicorn_port: int = Field(alias="webserver-port", default=8080, gt=0)
    web_concurrency: int = Field(alias="webserver-workers", default=1, gt=0)
    uvicorn_log_level: (
        typing.Literal["critical", "error", "warning", "info", "debug", "trace"]
    ) = Field(alias="webserver-log-level", default="info")
    app_metrics_port: int | None = Field(alias="metrics-port", default=None, gt=0)
    app_metrics_path: str | None = Field(alias="metrics-path", default=None, min_length=1)
    app_secret_key: str | None = Field(alias="secret-key", default=None, min_length=1)


class Charm(PaasCharm):
    """FastAPI Charm service.

    Attrs:
        framework_config_class: Base class for framework configuration.
    """

    framework_config_class = FastAPIConfig

    def __init__(self, framework: ops.Framework) -> None:
        """Initialize the FastAPI charm.

        Args:
            framework: operator framework.
        """
        super().__init__(framework=framework, framework_name="fastapi")

    @property
    def _workload_config(self) -> WorkloadConfig:
        """Return an WorkloadConfig instance."""
        framework_name = self._framework_name
        base_dir = pathlib.Path("/app")
        framework_config = typing.cast(FastAPIConfig, self.get_framework_config())
        return WorkloadConfig(
            framework=framework_name,
            container_name="app",
            port=framework_config.uvicorn_port,
            base_dir=base_dir,
            app_dir=base_dir,
            state_dir=base_dir / "state",
            service_name=framework_name,
            log_files=[],
            metrics_target=f"*:{framework_config.app_metrics_port}",
            metrics_path=framework_config.app_metrics_path,
        )

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
        return App(
            container=self._container,
            charm_state=charm_state,
            workload_config=self._workload_config,
            database_migration=self._database_migration,
            framework_config_prefix="",
        )