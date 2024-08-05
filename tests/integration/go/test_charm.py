# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Go charm."""

import requests
import typing

from juju.application import Application

WORKLOAD_PORT = 8080

async def test_go_is_up(
    go_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: build and deploy the go charm.
    act: send a request to the go application managed by the go charm.
    assert: the go application should return a correct response.
    """
    for unit_ip in await get_unit_ips(go_app.name):
        response = requests.get(f"http://{unit_ip}:{WORKLOAD_PORT}", timeout=5)
        assert response.status_code == 200
        assert "Hello, World!" in response.text
