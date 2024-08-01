# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the base class to represent the application."""

import abc
import logging

logger = logging.getLogger(__name__)


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
