# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Go charm unit tests for the generic app module."""

import pathlib
import unittest

from paas_app_charmer._generic.generic_app import GenericApp
from paas_app_charmer.app import AppConfig
from paas_app_charmer.charm_state import CharmState
from paas_app_charmer.go.charm import GoConfig


def test_go_env():
    framework_name = "go"
    framework_config = GoConfig.model_validate({"port": 8080})
    base_dir = pathlib.Path("/app")
    app_config = AppConfig(
        framework=framework_name,
        container_name="app",
        port=framework_config.port,
        base_dir=base_dir,
        app_dir=base_dir,
        state_dir=base_dir / "state",
        service_name=framework_name,
        log_files=[],
        metrics_target=f"*:{framework_config.metrics_port}",
        metrics_path=framework_config.metrics_path,
    )

    charm_state = CharmState(
        framework="go",
        secret_key="foobar",
        is_secret_storage_ready=True,
        framework_config=framework_config.dict(exclude_unset=True, exclude_none=True),
        # JAVI this is another app_config thing, the app_config. rename it?
        app_config={"otherconfig": "othervalue"},
    )

    app = GenericApp(
        container=unittest.mock.MagicMock(),
        charm_state=charm_state,
        app_config=app_config,
        database_migration=unittest.mock.MagicMock(),
    )
    env = app.gen_environment()
    assert env == {
        "APP_PORT": "8080",
        "APP_SECRET_KEY": "foobar",
        "APP_OTHERCONFIG": "othervalue",
    }
