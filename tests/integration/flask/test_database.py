#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Flask charm database integration."""
import asyncio
import logging

import juju
import ops
import pytest
import requests
from juju.application import Application
from pytest_operator.plugin import OpsTest

# caused by pytest fixtures
# pylint: disable=too-many-arguments

logger = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "endpoint,db_name, db_channel, revision, trust",
    [
        ("redis/status", "redis-k8s", "latest/edge", None, True),
        ("mysql/status", "mysql-k8s", "8.0/stable", "75", True),
        ("postgresql/status", "postgresql-k8s", "14/stable", None, True),
        ("mongodb/status", "mongodb-k8s", "6/beta", None, True),
    ],
)
async def test_with_database(
    ops_test: OpsTest,
    flask_app: Application,
    model: juju.model.Model,
    get_unit_ips,
    endpoint: str,
    db_name: str,
    db_channel: str,
    revision: str | None,
    trust: bool,
):
    """
    arrange: build and deploy the flask charm.
    act: deploy the database and relate it to the charm.
    assert: requesting the charm should return a correct response
    """
    deploy_cmd = ["deploy", db_name, "--channel", db_channel]
    if revision:
        deploy_cmd.extend(["--revision", revision])
    if trust:
        deploy_cmd.extend(["--trust"])
    await ops_test.juju(*deploy_cmd)

    # mypy doesn't see that ActiveStatus has a name
    await model.wait_for_idle(status=ops.ActiveStatus.name)  # type: ignore

    await model.add_relation(flask_app.name, db_name)

    # mypy doesn't see that ActiveStatus has a name
    await model.wait_for_idle(status=ops.ActiveStatus.name)  # type: ignore

    for unit_ip in await get_unit_ips(flask_app.name):
        for _ in range(10):
            response = requests.get(f"http://{unit_ip}:8000/{endpoint}", timeout=5)
            assert response.status_code == 200
            if "SUCCESS" == response.text:
                return
            await asyncio.sleep(60)
        assert "SUCCESS" == response.text
