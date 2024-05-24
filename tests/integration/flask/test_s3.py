# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Flask charm s3 integration."""
import logging
from secrets import token_hex

import juju
import ops
import requests
from juju.application import Application
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)


async def test_s3_integration(
    ops_test: OpsTest,
    flask_app: Application,
    model: juju.model.Model,
    get_unit_ips,
):
    """
    TODO.
    """
    s3_config = {
        "endpoint": f"http://s3.example.com",
        "bucket": "mybucket",
        "path": "/flask",
        "region": "us-east-1",
        "s3-uri-style": "path",
    }
    s3_credentials = {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
    }
    s3_integrator_app = await model.deploy(
        "s3-integrator",
        channel="latest/edge",
        config=s3_config,
    )
    await model.wait_for_idle(apps=[s3_integrator_app.name], idle_period=5, status="blocked")
    action_sync_s3_credentials: Action = await s3_integrator_app.units[0].run_action(
        "sync-s3-credentials",
        **s3_credentials,
    )
    await action_sync_s3_credentials.wait()
    await model.wait_for_idle(status="active")

    await model.add_relation(f"{s3_integrator_app.name}", f"{flask_app.name}")
    await model.wait_for_idle(
        idle_period=30,
        apps=[flask_app.name, s3_integrator_app.name],
        status="active",
    )

    for unit_ip in await get_unit_ips(flask_app.name):
        for _ in range(10):
            response = requests.get(f"http://{unit_ip}:8000/env", timeout=5)
            assert response.status_code == 200
            env = response.json()
            assert env["S3_ACCESS_KEY"] == s3_credentials["access-key"]
            assert env["S3_SECRET_KEY"] == s3_credentials["secret-key"]
            assert env["S3_BUCKET"] == s3_config["bucket"]
            assert env["S3_ENDPOINT"] == s3_config["endpoint"]
            assert env["S3_PATH"] == s3_config["path"]
            assert env["S3_REGION"] == s3_config["region"]
            # JAVI THIS IS NOT NICE S3_S3
            assert env["S3_S3_URI_STYLE"] == s3_config["s3-uri-style"]
