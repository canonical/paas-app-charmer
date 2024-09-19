# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Flask workers and schedulers."""

import asyncio
import logging
import time

import requests
from juju.application import Application
from juju.model import Model
from juju.utils import block_until
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)


async def test_workers_services_one_node(
    ops_test: OpsTest, model: Model, flask_app: Application, get_unit_ips
):
    """
    arrange: TODO
    act: TODO
    assert: TODO
    """
    redis_app_name = "redis-k8s"
    redis_app = await model.deploy(redis_app_name, channel="edge")
    await model.wait_for_idle(apps=[redis_app.name], status="active")

    await model.integrate(flask_app.name, redis_app.name)
    await model.wait_for_idle(apps=[redis_app.name, flask_app.name], status="active")

    # the flask unit is not important
    flask_unit_ip = (await get_unit_ips(flask_app.name))[0]

    # clean the current celery stats
    response = requests.get(f"http://{flask_unit_ip}:8000/redis/clear_celery_stats", timeout=5)
    assert response.status_code == 200
    assert "SUCCESS" == response.text

    def check_correct_celery_stats(num_schedulers, num_workers):
        """Check that the expected number of workers and schedulers is right."""
        response = requests.get(f"http://{flask_unit_ip}:8000/redis/celery_stats", timeout=5)
        assert response.status_code == 200
        data = response.json()
        logger.info(
            "check_correct_celery_stats. Expected schedulers: %d, expected workers %d. Result %s",
            num_schedulers,
            num_workers,
            data,
        )
        return len(data["workers"]) == num_workers and len(data["schedulers"]) == num_schedulers

    time.sleep(3)  # enough time for all the schedulers to send messages
    try:
        await block_until(
            lambda: check_correct_celery_stats(num_schedulers=1, num_workers=1),
            timeout=20,
            wait_period=1,
        )
    except asyncio.TimeoutError:
        assert False, "Failed to get 1 worker and 1 scheduler"

    await flask_app.scale(2)
    await model.wait_for_idle(apps=[flask_app.name], status="active")

    # clean the current celery stats
    response = requests.get(f"http://{flask_unit_ip}:8000/redis/clear_celery_stats", timeout=5)
    assert response.status_code == 200
    assert "SUCCESS" == response.text

    time.sleep(3)  # enough time for all the schedulers to send messages
    try:
        await block_until(
            lambda: check_correct_celery_stats(num_schedulers=1, num_workers=2),
            timeout=60,
            wait_period=1,
        )
    except asyncio.TimeoutError:
        assert False, "Failed to get 2 workers and 1 scheduler"
