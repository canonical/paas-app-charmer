# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging

import pytest
import pytest_asyncio
from juju.application import Application
from juju.client.jujudata import FileJujuData
from juju.juju import Juju
from juju.model import Controller, Model
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="module", name="ops_test_lxd")
async def ops_test_lxd_fixture(request, tmp_path_factory, ops_test: OpsTest):
    # Create lxd controller if it does not exist
    if not "lxd" in Juju().get_controllers():
        jujudata = FileJujuData()
        previous_controller = jujudata.current_controller()
        logger.info("bootstrapping lxd")
        _, _, _ = await ops_test.juju("bootstrap", "localhost", "lxd", check=True)
        # go back to the original controller
        logger.info("switch back to controller: %s", previous_controller)
        _, _, _ = await ops_test.juju("switch", previous_controller, check=True)

    ops_test = OpsTest(request, tmp_path_factory)
    ops_test.controller_name = "lxd"
    await ops_test._setup_model()
    # The instance is not stored in _instance as that is done for the ops_test fixture
    yield ops_test
    await ops_test._cleanup_models()


@pytest_asyncio.fixture(scope="module", name="lxd_model")
async def lxd_model_fixture(ops_test_lxd: OpsTest) -> Model:
    """Return the current lxd juju model."""
    assert ops_test_lxd.model
    return ops_test_lxd.model


@pytest_asyncio.fixture(scope="module", name="rabbitmq_server_app")  # autouse=True)
async def deploy_rabbitmq_server_fixture(
    lxd_model: Model,
) -> Application:
    """Deploy rabbitmq-server machine app."""
    app = await lxd_model.deploy(
        "rabbitmq-server",
        # channel="3.9/stable",
        channel="latest/edge",
    )
    await lxd_model.wait_for_idle(raise_on_blocked=True)
    offer = await lxd_model.create_offer("rabbitmq-server:amqp")
    logger.info("offer: %s", offer)
    offers = await lxd_model.list_offers()
    logger.info("offers: %s", offers)
    yield app


@pytest_asyncio.fixture(scope="module", name="rabbitmq_k8s_app")  # autouse=True)
async def deploy_rabbitmq_k8s_fixture(
    model: Model,
) -> Application:
    """Deploy rabbitmq-server machine app."""
    app = await model.deploy(
        "rabbitmq-k8s",
        channel="3.12/edge",
        trust=True,
    )
    await model.wait_for_idle(raise_on_blocked=True)
    yield app


@pytest_asyncio.fixture(scope="module", name="get_unit_ips")
async def fixture_get_unit_ips(ops_test: OpsTest):
    """Return an async function to retrieve unit ip addresses of a certain application."""

    async def get_unit_ips(application_name: str):
        """Retrieve unit ip addresses of a certain application.

        Returns:
            A list containing unit ip addresses.
        """
        _, status, _ = await ops_test.juju("status", "--format", "json")
        status = json.loads(status)
        units = status["applications"][application_name]["units"]
        return tuple(
            unit_status["address"]
            for _, unit_status in sorted(units.items(), key=lambda kv: int(kv[0].split("/")[-1]))
        )

    return get_unit_ips


@pytest_asyncio.fixture(scope="module", name="model")
async def fixture_model(ops_test: OpsTest) -> Model:
    """Return the current testing juju model."""
    assert ops_test.model
    return ops_test.model


@pytest.fixture(scope="module", name="external_hostname")
def external_hostname_fixture() -> str:
    """Return the external hostname for ingress-related tests."""
    return "juju.test"


@pytest.fixture(scope="module", name="traefik_app_name")
def traefik_app_name_fixture() -> str:
    """Return the name of the traefik application deployed for tests."""
    return "traefik-k8s"


@pytest.fixture(scope="module", name="prometheus_app_name")
def prometheus_app_name_fixture() -> str:
    """Return the name of the prometheus application deployed for tests."""
    return "prometheus-k8s"


@pytest.fixture(scope="module", name="loki_app_name")
def loki_app_name_fixture() -> str:
    """Return the name of the prometheus application deployed for tests."""
    return "loki-k8s"


@pytest.fixture(scope="module", name="grafana_app_name")
def grafana_app_name_fixture() -> str:
    """Return the name of the grafana application deployed for tests."""
    return "grafana-k8s"


@pytest_asyncio.fixture(scope="module", name="prometheus_app")
async def deploy_prometheus_fixture(
    model: Model,
    prometheus_app_name: str,
):
    """Deploy prometheus."""
    app = await model.deploy(
        "prometheus-k8s",
        application_name=prometheus_app_name,
        channel="1.0/stable",
        revision=129,
        series="focal",
        trust=True,
    )
    await model.wait_for_idle(raise_on_blocked=True)

    return app


@pytest_asyncio.fixture
def run_action(ops_test: OpsTest):
    async def _run_action(application_name, action_name, **params):
        app = ops_test.model.applications[application_name]
        action = await app.units[0].run_action(action_name, **params)
        await action.wait()
        return action.results

    return _run_action
