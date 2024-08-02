# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the base class to represent the application."""

import abc
import logging
import pathlib
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class AppConfig:  # pylint: disable=too-many-instance-attributes
    """Base Configuration for App.

    This class contains attributes that are configuration for the app/workload.

    Attrs:
        framework: the framework name.
        container_name: The container name.
        port: the port number to use for the server.
        user: The UNIX user name for running the service.
        group: The UNIX group name for running the service.
        base_dir: The project base directory in the application container.
        app_dir: The application directory in the application container.
        state_dir: the directory in the application container to store states information.
        service_name: The WSGI application pebble service name.
        log_files: List of files to monitor.
    """

    framework: str
    container_name: str
    port: int
    user: str = "_daemon_"
    group: str = "_daemon_"
    base_dir: pathlib.Path
    app_dir: pathlib.Path
    state_dir: pathlib.Path
    service_name: str
    log_files: List[pathlib.Path]


class App(abc.ABC):
    """Base class for the application manager."""

    @abc.abstractmethod
    def gen_environment(self) -> dict[str, str]:
        """Generate a environment dictionary from the charm configurations."""

    @abc.abstractmethod
    def stop_all_services(self) -> None:
        """Stop all the services in the workload."""

    @abc.abstractmethod
    def restart(self) -> None:
        """Restart or start the WSGI service if not started with the latest configuration."""
