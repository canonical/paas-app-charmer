# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Observability class to represent the observability stack for charms."""
import os.path
import pathlib
import typing

import ops
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider


class ObservabilityCharmState(typing.Protocol):
    """CharmState interface required by Observability class.

    Attrs:
        application_log_file: the path to the application's main log file.
        application_error_log_file: the path to the application's error error file.
    """

    @property
    def application_log_file(self) -> pathlib.Path:
        """Return the path to the application's main log file.

        Returns:
            The path to the application's main log file.
        """

    @property
    def application_error_log_file(self) -> pathlib.Path:
        """Return the path to the application's error log file.

        Returns:
            The path to the application's error log file.
        """


class Observability(ops.Object):  # pylint: disable=too-few-public-methods
    """A class representing the observability stack for charm managed application."""

    def __init__(
        self,
        charm: ops.CharmBase,
        charm_state: ObservabilityCharmState,
        container_name: str,
        cos_dir: str,
    ):
        """Initialize a new instance of the Observability class.

        Args:
            charm: The charm object that the Observability instance belongs to.
            charm_state: The state of the charm that the Observability instance belongs to.
            container_name: The name of the application container.
            cos_dir: The directories containing the grafana_dashboards, loki_alert_rules and
                prometheus_alert_rules.
        """
        super().__init__(charm, "observability")
        self._charm = charm
        self._metrics_endpoint = MetricsEndpointProvider(
            charm,
            alert_rules_path=os.path.join(cos_dir, "prometheus_alert_rules"),
            jobs=[{"static_configs": [{"targets": ["*:9102"]}]}],
            relation_name="metrics-endpoint",
        )
        self._logging = LogProxyConsumer(
            charm,
            alert_rules_path=os.path.join(cos_dir, "loki_alert_rules"),
            container_name=container_name,
            log_files=[
                str(charm_state.application_log_file),
                str(charm_state.application_error_log_file),
            ],
            relation_name="logging",
        )
        self._grafana_dashboards = GrafanaDashboardProvider(
            charm,
            dashboards_path=os.path.join(cos_dir, "grafana_dashboards"),
            relation_name="grafana-dashboard",
        )
