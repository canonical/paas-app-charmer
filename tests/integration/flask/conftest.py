# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for flask charm integration tests."""

import os
import pathlib

import pytest
import pytest_asyncio
from juju.application import Application
from juju.model import Model
from pytest import Config, FixtureRequest
from pytest_operator.plugin import OpsTest

from tests.integration.helpers import inject_charm_config, inject_venv

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.parent


@pytest.fixture(autouse=True)
def cwd():
    return os.chdir(PROJECT_ROOT / "examples/flask")


@pytest.fixture(scope="module", name="test_flask_image")
def fixture_test_flask_image(pytestconfig: Config):
    """Return the --test-flask-image test parameter."""
    test_flask_image = pytestconfig.getoption("--test-flask-image")
    if not test_flask_image:
        raise ValueError("the following arguments are required: --test-flask-image")
    return test_flask_image


@pytest.fixture(scope="module", name="test_db_flask_image")
def fixture_test_db_flask_image(pytestconfig: Config):
    """Return the --test-flask-image test parameter."""
    test_flask_image = pytestconfig.getoption("--test-db-flask-image")
    if not test_flask_image:
        raise ValueError("the following arguments are required: --test-db-flask-image")
    return test_flask_image


@pytest_asyncio.fixture(scope="module", name="charm_file")
async def charm_file_fixture(pytestconfig: pytest.Config, ops_test: OpsTest) -> pathlib.Path:
    """Get the existing charm file."""
    charm_file = pytestconfig.getoption("--charm-file")
    if not charm_file:
        charm_file = await ops_test.build_charm(PROJECT_ROOT / "examples/flask")
    elif charm_file[0] != "/":
        charm_file = PROJECT_ROOT / charm_file
    inject_venv(charm_file, PROJECT_ROOT / "paas_app_charmer")
    return pathlib.Path(charm_file).absolute()


@pytest_asyncio.fixture(scope="module", name="build_charm")
async def build_charm_fixture(charm_file: str, tmp_path_factory) -> str:
    """Build the charm and injects additional configurations into config.yaml.

    This fixture is designed to simulate a feature that is not yet available in charmcraft that
    allows for the modification of charm configurations during the build process.
    Three additional configurations, namely foo_str, foo_int, foo_dict, foo_bool,
    and application_root will be appended to the config.yaml file.
    """
    return inject_charm_config(
        charm_file,
        {
            "foo-str": {"type": "string"},
            "foo-int": {"type": "int"},
            "foo-bool": {"type": "boolean"},
            "foo-dict": {"type": "string"},
            "application-root": {"type": "string"},
        },
        tmp_path_factory.mktemp("flask"),
    )


@pytest_asyncio.fixture(scope="module", name="flask_app")
async def flask_app_fixture(build_charm: str, model: Model, test_flask_image: str):
    """Build and deploy the flask charm."""
    app_name = "flask-k8s"

    resources = {
        "flask-app-image": test_flask_image,
    }
    app = await model.deploy(
        build_charm, resources=resources, application_name=app_name, series="jammy"
    )
    await model.wait_for_idle(raise_on_blocked=True)
    return app


@pytest_asyncio.fixture(scope="module", name="flask_db_app")
async def flask_db_app_fixture(build_charm: str, model: Model, test_db_flask_image: str):
    """Build and deploy the flask charm with test-db-flask image."""
    app_name = "flask-k8s"

    resources = {
        "flask-app-image": test_db_flask_image,
    }
    app = await model.deploy(
        build_charm, resources=resources, application_name=app_name, series="jammy"
    )
    await model.wait_for_idle()
    return app


@pytest_asyncio.fixture(scope="module", name="traefik_app")
async def deploy_traefik_fixture(
    model: Model,
    flask_app,  # pylint: disable=unused-argument
    traefik_app_name: str,
    external_hostname: str,
):
    """Deploy traefik."""
    app = await model.deploy(
        "traefik-k8s",
        application_name=traefik_app_name,
        channel="edge",
        trust=True,
        config={
            "external_hostname": external_hostname,
            "routing_mode": "subdomain",
        },
    )
    await model.wait_for_idle(raise_on_blocked=True)

    return app


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


@pytest_asyncio.fixture(scope="module", name="loki_app")
async def deploy_loki_fixture(
    model: Model,
    loki_app_name: str,
):
    """Deploy loki."""
    app = await model.deploy(
        "loki-k8s", application_name=loki_app_name, channel="latest/stable", trust=True
    )
    await model.wait_for_idle(raise_on_blocked=True)

    return app


@pytest_asyncio.fixture(scope="module", name="cos_apps")
async def deploy_cos_fixture(
    model: Model,
    loki_app,  # pylint: disable=unused-argument
    prometheus_app,  # pylint: disable=unused-argument
    grafana_app_name: str,
):
    """Deploy the cos applications."""
    cos_apps = await model.deploy(
        "grafana-k8s",
        application_name=grafana_app_name,
        channel="1.0/stable",
        revision=82,
        series="focal",
        trust=True,
    )
    await model.wait_for_idle(status="active")
    return cos_apps


@pytest_asyncio.fixture
async def update_config(model: Model, request: FixtureRequest, flask_app: Application):
    """Update the flask application configuration.

    This fixture must be parameterized with changing charm configurations.
    """
    orig_config = {k: v.get("value") for k, v in (await flask_app.get_config()).items()}
    request_config = {k: str(v) for k, v in request.param.items()}
    await flask_app.set_config(request_config)
    await model.wait_for_idle(apps=[flask_app.name])

    yield request_config

    await flask_app.set_config(
        {k: v for k, v in orig_config.items() if k in request_config and v is not None}
    )
    await flask_app.reset_config([k for k in request_config if orig_config[k] is None])
    await model.wait_for_idle(apps=[flask_app.name])
