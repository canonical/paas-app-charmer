# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Generic utility functions."""

import itertools

import ops
from pydantic import ValidationError


def build_validation_error_message(
    exc: ValidationError, prefix: str | None = None, underscore_to_dash: bool = False
) -> str:
    """Build a str with a list of error fields from a pydantic exception.

    Args:
        exc: ValidationError exception instance.
        prefix: Prefix to append to the error field names.
        underscore_to_dash: Replace underscores to dashes in the error field names.

    Returns:
        The curated list of error fields ready to be used in an error message.
    """
    error_fields_unique = set(
        itertools.chain.from_iterable(error["loc"] for error in exc.errors())
    )
    error_fields = (str(error_field) for error_field in error_fields_unique)
    if prefix:
        error_fields = (f"{prefix}{error_field}" for error_field in error_fields)
    if underscore_to_dash:
        error_fields = (error_field.replace("_", "-") for error_field in error_fields)
    error_field_str = " ".join(error_fields)
    return error_field_str


def enable_pebble_log_forwarding() -> bool:
    """Check if the current environment allows to enable pebble log forwarding feature.

    Returns:
        True if the current environment allows to enable pebble log forwarding feature.
    """
    juju_version = ops.JujuVersion.from_environ()
    if (juju_version.major, juju_version.minor) < (3, 4):
        return False
    try:
        # disable "imported but unused" and "import outside toplevel" error
        # pylint: disable=import-outside-toplevel,unused-import
        import charms.loki_k8s.v1.loki_push_api  # noqa: F401

        return True
    except ImportError:
        return False
