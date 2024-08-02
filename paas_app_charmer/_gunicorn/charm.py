# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The base charm class for all charms."""
import logging

from paas_app_charmer._gunicorn.webserver import GunicornWebserver, WebserverConfig
from paas_app_charmer._gunicorn.workload_config import create_app_config
from paas_app_charmer._gunicorn.wsgi_app import WsgiApp
from paas_app_charmer.app import App, AppConfig
from paas_app_charmer.charm import PaasCharm

logger = logging.getLogger(__name__)


class GunicornBase(PaasCharm):
    """Gunicorn-based charm service mixin."""

    @property
    def _app_config(self) -> AppConfig:
        """Return an AppConfig instance."""
        return create_app_config(self._framework_name)

    def _create_app(self) -> App:
        """Build a App instance.

        Returns:
            A new App instance.
        """
        charm_state = self._create_charm_state()

        webserver = GunicornWebserver(
            webserver_config=WebserverConfig.from_charm_state(charm_state),
            app_config=self._app_config,
            container=self.unit.get_container(self._app_config.container_name),
        )

        return WsgiApp(
            container=self._container,
            charm_state=charm_state,
            app_config=self._app_config,
            webserver=webserver,
            database_migration=self._database_migration,
        )
