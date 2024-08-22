# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Global fixtures and utilities for integration and unit tests."""


def pytest_addoption(parser):
    """Define some command line options for integration and unit tests."""
    parser.addoption("--charm-file", action="extend", nargs="+", default=[])
    parser.addoption("--test-flask-image", action="store")
    parser.addoption("--test-db-flask-image", action="store")
    parser.addoption("--django-app-image", action="store")
    parser.addoption("--fastapi-app-image", action="store")
    parser.addoption("--go-app-image", action="store")
    parser.addoption("--localstack-address", action="store")
