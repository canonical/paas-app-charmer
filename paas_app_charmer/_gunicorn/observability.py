# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Observability class to represent the observability stack for charms."""
import os.path

import ops
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider

from paas_app_charmer._gunicorn import logrotate
from paas_app_charmer._gunicorn.charm_state import CharmState


class Observability(ops.Object):  # pylint: disable=too-few-public-methods
    """A class representing the observability stack for charm managed application."""

    def __init__(
        self,
        charm: ops.CharmBase,
        charm_state: CharmState,
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
        self._charm_state = charm_state
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
            log_files=["/var/log/**/*.log", "/var/log/*.log"],
            relation_name="logging",
        )
        self._grafana_dashboards = GrafanaDashboardProvider(
            charm,
            dashboards_path=os.path.join(cos_dir, "grafana_dashboards"),
            relation_name="grafana-dashboard",
        )
        container_name = charm_state.container_name.replace("-", "_")
        self.framework.observe(
            getattr(self._charm.on, f"{container_name}_pebble_ready"),
            self._install_logrotate,
        )

    def _install_logrotate(self, _event: ops.PebbleReadyEvent) -> None:
        """Install and start logrotate service in the application container."""
        container = self._charm.unit.get_container(self._charm_state.container_name)
        with open(logrotate.__file__, encoding="utf-8") as f:
            log_rotate_script = f.read()
        container.push("/bin/logrotate.py", log_rotate_script, encoding="utf-8", permissions=0o555)
        container.add_layer(
            "logrotate.py",
            {
                "services": {
                    "logrotate.py": {
                        "override": "replace",
                        "command": f"/bin/logrotate.py --framework {self._charm_state.framework}",
                        "startup": "enabled",
                    }
                }
            },
            combine=True,
        )
        container.start("logrotate.py")
