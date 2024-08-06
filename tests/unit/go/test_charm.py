# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Go charm unit tests."""

import unittest

import ops
import pytest
from ops.testing import Harness

from .constants import DEFAULT_LAYER, GO_CONTAINER_NAME


@pytest.mark.parametrize(
    "config, env",
    [
        pytest.param(
            {},
            {
                "APP_PORT": "8080",
                "APP_BASE_URL": "http://go-k8s.None:8080",
                "APP_METRICS_PORT": "8080",
                "APP_METRICS_PATH": "/metrics",
                "APP_SECRET_KEY": "test",
            },
            id="default",
        ),
        # JAVI pending test for metrics port and path different.
    ],
)
def test_go_config(harness: Harness, config: dict, env: dict) -> None:
    """
    arrange: none
    act: start the go charm and set go-app container to be ready.
    assert: go charm should submit the correct go pebble layer to pebble.
    """
    container = harness.model.unit.get_container(GO_CONTAINER_NAME)
    container.add_layer("a_layer", DEFAULT_LAYER)
    harness.begin_with_initial_hooks()
    harness.charm._secret_storage.get_secret_key = unittest.mock.MagicMock(return_value="test")
    harness.update_config(config)

    assert harness.model.unit.status == ops.ActiveStatus()
    plan = container.get_plan()
    go_layer = plan.to_dict()["services"]["go"]
    assert go_layer == {
        "environment": env,
        "override": "replace",
        "startup": "enabled",
        "command": "/usr/local/bin/go-k8s",
        "user": "_daemon_",
        "working-dir": "/app",
    }


# JAVI pending test for metrics port and path in observability relation check relation data.
