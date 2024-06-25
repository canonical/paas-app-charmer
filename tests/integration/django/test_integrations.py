# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Django charm integrations."""

import pytest
import requests
from juju.model import Model


async def test_blocking_and_restarting_on_required_integration(
    model: Model, django_app, get_unit_ips
):
    """
    arrange:
    act:
    assert:
    """

    unit_ip = (await get_unit_ips(django_app.name))[0]
    response = requests.get(f"http://{unit_ip}:8000/len/users", timeout=5)
    assert response.status_code == 200

    # remove integration and check service is stopped
    await django_app.destroy_relation("postgresql", "postgresql-k8s:database")

    await model.wait_for_idle(apps=[django_app.name], status="blocked")
    unit_ip = (await get_unit_ips(django_app.name))[0]
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get(f"http://{unit_ip}:8000/len/users", timeout=5)

    # add integration again and check service gets started
    await model.integrate(django_app.name, "postgresql-k8s")
    await model.wait_for_idle(status="active")

    unit_ip = (await get_unit_ips(django_app.name))[0]
    response = requests.get(f"http://{unit_ip}:8000/len/users", timeout=5)
    assert response.status_code == 200
