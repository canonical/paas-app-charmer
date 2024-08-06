# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Go charm."""

import typing

import requests
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


        
async def test_migration(
    go_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange:
    act:
    assert:
    """
    # before and after integrating with postgresql?
    for unit_ip in await get_unit_ips(go_app.name):
        response = requests.get(f"http://{unit_ip}:{WORKLOAD_PORT}/postgresql/status", timeout=5)
        assert response.status_code == 200
        assert "SUCCESS" in response.text


# async def test_env_variables
# metrics to an specific port could be nice? async def test_env_variables
