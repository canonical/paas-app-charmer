# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Some helper functions."""

import pathlib

import yaml


def load_requires() -> dict:
    """Return the required integration defined in charm metadata.

    Returns:
        The requires section of the charm metadata.
    """
    metadata_file = pathlib.Path("metadata.yaml")
    if not metadata_file.exists():
        metadata_file = pathlib.Path("charmcraft.yaml")
    metadata = yaml.safe_load(metadata_file.read_text(encoding="utf-8"))
    return metadata.get("requires", {})
