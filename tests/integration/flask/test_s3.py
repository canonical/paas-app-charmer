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
    s3_configuration,
    s3_credentials,
    boto_s3_client,
):
    """
    arrange: build and deploy the flask charm. Create the s3 bucket.
    act: Integrate the charm with the s3-integrator.
    assert: the flask application should return in the endpoint /env
       the correct S3 env variables.
    """
    bucket_name = s3_configuration["bucket"]
    boto_s3_client.create_bucket(Bucket=bucket_name)

    s3_integrator_app = await model.deploy(
        "s3-integrator",
        channel="latest/edge",
        config=s3_configuration,
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
        response = requests.get(f"http://{unit_ip}:8000/env", timeout=5)
        assert response.status_code == 200
        env = response.json()
        assert env["S3_ACCESS_KEY"] == s3_credentials["access-key"]
        assert env["S3_SECRET_KEY"] == s3_credentials["secret-key"]
        assert env["S3_BUCKET"] == s3_configuration["bucket"]
        assert env["S3_ENDPOINT"] == s3_configuration["endpoint"]
        assert env["S3_PATH"] == s3_configuration["path"]
        assert env["S3_REGION"] == s3_configuration["region"]
        assert env["S3_URI_STYLE"] == s3_configuration["s3-uri-style"]

        # Check that it list_objects in the bucket. If the connection
        # is unsuccessful of the bucket does not exist, the code raises.
        response = requests.get(f"http://{unit_ip}:8000/s3/status", timeout=5)
        assert response.status_code == 200
        assert "SUCCESS" == response.text
