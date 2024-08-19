# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""pytest fixtures for the fastapi unit test."""
import os
import pathlib
import shlex
import typing
import unittest.mock

import ops
import pytest
from ops.testing import Harness

from examples.fastapi.charm.src.charm import FastAPICharm

from .constants import DEFAULT_LAYER, FASTAPI_CONTAINER_NAME

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.parent


@pytest.fixture(autouse=True, scope="package")
def cwd():
    return os.chdir(PROJECT_ROOT / "examples/fastapi/charm")


@pytest.fixture(name="harness")
def harness_fixture() -> typing.Generator[Harness, None, None]:
    """Ops testing framework harness fixture."""
    harness = Harness(FastAPICharm)
    harness.set_leader()
    root = harness.get_filesystem_root(FASTAPI_CONTAINER_NAME)
    (root / "app").mkdir(parents=True)
    harness.set_can_connect(FASTAPI_CONTAINER_NAME, True)

    yield harness
    harness.cleanup()
