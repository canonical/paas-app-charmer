# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the GunicornWebserver class to represent the gunicorn server."""
import dataclasses
import datetime
import logging
import pathlib
import shlex
import signal
import typing

import ops
from ops.pebble import ExecError, PathError

from paas_app_charmer._gunicorn.workload_config import (
    APPLICATION_ERROR_LOG_FILE_FMT,
    APPLICATION_LOG_FILE_FMT,
    STATSD_HOST,
)
from paas_app_charmer.app import WorkloadConfig
from paas_app_charmer.exceptions import CharmConfigInvalidError

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class WebserverConfig:
    """Represent the configuration values for a web server.

    Attributes:
        workers: The number of workers to use for the web server, or None if not specified.
        threads: The number of threads per worker to use for the web server,
            or None if not specified.
        keepalive: The time to wait for requests on a Keep-Alive connection,
            or None if not specified.
        timeout: The request silence timeout for the web server, or None if not specified.
    """

    workers: int | None = None
    threads: int | None = None
    keepalive: datetime.timedelta | None = None
    timeout: datetime.timedelta | None = None

    def items(self) -> typing.Iterable[tuple[str, int | datetime.timedelta | None]]:
        """Return the dataclass values as an iterable of the key-value pairs.

        Returns:
            An iterable of the key-value pairs.
        """
        return {
            "workers": self.workers,
            "threads": self.threads,
            "keepalive": self.keepalive,
            "timeout": self.timeout,
        }.items()

    @classmethod
    def from_charm_config(cls, config: dict[str, int | float | str | bool]) -> "WebserverConfig":
        """Create a WebserverConfig object from a charm state object.

        Args:
            config: The charm config as a dict.

        Returns:
            A WebserverConfig object.
        """
        keepalive = config.get("webserver-keepalive")
        timeout = config.get("webserver-timeout")
        workers = config.get("webserver-workers")
        threads = config.get("webserver-threads")
        return cls(
            workers=int(typing.cast(str, workers)) if workers is not None else None,
            threads=int(typing.cast(str, threads)) if threads is not None else None,
            keepalive=(
                datetime.timedelta(seconds=int(keepalive)) if keepalive is not None else None
            ),
            timeout=(datetime.timedelta(seconds=int(timeout)) if timeout is not None else None),
        )


class GunicornWebserver:  # pylint: disable=too-few-public-methods
    """A class representing a Gunicorn web server."""

    def __init__(
        self,
        webserver_config: WebserverConfig,
        workload_config: WorkloadConfig,
        container: ops.Container,
    ):
        """Initialize a new instance of the GunicornWebserver class.

        Args:
            webserver_config: the Gunicorn webserver configuration.
            workload_config: The state of the workload that the GunicornWebserver belongs to.
            container: The WSGI application container in this charm unit.
        """
        self._webserver_config = webserver_config
        self._workload_config = workload_config
        self._container = container
        self._reload_signal = signal.SIGHUP

    @property
    def _config(self) -> str:
        """Generate the content of the Gunicorn configuration file based on charm states.

        Returns:
            The content of the Gunicorn configuration file.
        """
        config_entries = []
        for setting, setting_value in self._webserver_config.items():
            setting_value = typing.cast(None | int | datetime.timedelta, setting_value)
            if setting_value is None:
                continue
            setting_value = (
                setting_value
                if isinstance(setting_value, int)
                else int(setting_value.total_seconds())
            )
            config_entries.append(f"{setting} = {setting_value}")
        new_line = "\n"
        config = f"""\
bind = ['0.0.0.0:{self._workload_config.port}']
chdir = {repr(str(self._workload_config.app_dir))}
accesslog = {repr(str.format(APPLICATION_LOG_FILE_FMT, framework=self._workload_config.framework))}
errorlog = {repr(str.format(APPLICATION_ERROR_LOG_FILE_FMT,
                            framework=self._workload_config.framework))}
statsd_host = {repr(STATSD_HOST)}
{new_line.join(config_entries)}"""
        return config

    @property
    def _config_path(self) -> pathlib.Path:
        """Gets the path to the Gunicorn configuration file.

        Returns:
            The path to the web server configuration file.
        """
        return self._workload_config.base_dir / "gunicorn.conf.py"

    def update_config(
        self, environment: dict[str, str], is_webserver_running: bool, command: str
    ) -> None:
        """Update and apply the configuration file of the web server.

        Args:
            environment: Environment variables used to run the application.
            is_webserver_running: Indicates if the web server container is currently running.
            command: The WSGI application startup command.

        Raises:
            CharmConfigInvalidError: if the charm configuration is not valid.
        """
        self._prepare_log_dir()
        webserver_config_path = str(self._config_path)
        try:
            current_webserver_config = self._container.pull(webserver_config_path)
        except PathError:
            current_webserver_config = None
        self._container.push(webserver_config_path, self._config)
        if current_webserver_config == self._config:
            return
        check_config_command = shlex.split(command)
        check_config_command.append("--check-config")
        exec_process = self._container.exec(
            check_config_command,
            environment=environment,
            user=self._workload_config.user,
            group=self._workload_config.group,
            working_dir=str(self._workload_config.app_dir),
        )
        try:
            exec_process.wait_output()
        except ExecError as exc:
            logger.error(
                "webserver configuration check failed, stdout: %s, stderr: %s",
                exc.stdout,
                exc.stderr,
            )
            raise CharmConfigInvalidError(
                "Webserver configuration check failed, "
                "please review your charm configuration or database relation"
            ) from exc
        if is_webserver_running:
            logger.info("gunicorn config changed, reloading")
            self._container.send_signal(self._reload_signal, self._workload_config.service_name)

    def _prepare_log_dir(self) -> None:
        """Prepare access and error log directory for the application."""
        container = self._container
        for log in self._workload_config.log_files:
            log_dir = str(log.parent.absolute())
            if not container.exists(log_dir):
                container.make_dir(
                    log_dir,
                    make_parents=True,
                    user=self._workload_config.user,
                    group=self._workload_config.group,
                )
