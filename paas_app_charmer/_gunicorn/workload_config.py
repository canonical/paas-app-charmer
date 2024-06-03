# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""This module defines the WorloadConfig class which represents configuration for the workload."""

import pathlib


# too-many-instance-attributes as this class is basically configuration.
class WorkloadConfig:  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """Configuration for the workload.

    This class container attributes that are configuration for the
    workload.

    Attrs:
        statsd_host: the statsd server host for WSGI application metrics.
        port: the port number to use for the server.
        user: The UNIX user name for running the service.
        group: The UNIX group name for running the service.
        container_name: The container name.
        application_log_file: the file path for the application access log.
        application_error_log_file: the file path for the application error log.
        base_dir: The project base directory in the application container.
        app_dir: The application directory in the application container.
        state_dir: the directory in the application container to store states information.
        service_name: The WSGI application pebble service name.
        log_files: List of files to monitor.
    """

    statsd_host = "localhost:9125"
    port = 8000
    user = "_daemon_"
    group = "_daemon_"

    def __init__(self, framework: str):
        """Initialize a new instance of the WorkloadConfig class.

        Args:
            framework: the framework name.
        """
        self.framework = framework
        self.container_name = f"{self.framework}-app"
        self.base_dir = pathlib.Path(f"/{framework}")
        self.application_log_file = pathlib.Path(f"/var/log/{self.framework}/access.log")
        self.application_error_log_file = pathlib.Path(f"/var/log/{self.framework}/error.log")
        self.base_dir = pathlib.Path(f"/{framework}")
        self.app_dir = self.base_dir / "app"
        self.state_dir = self.base_dir / "state"
        self.service_name = self.framework

    @property
    def log_files(self) -> list[str | pathlib.Path]:
        """Return list of log files to monitor."""
        return [
            self.application_log_file,
            self.application_error_log_file,
        ]
