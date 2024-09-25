# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Framework related base classes."""
import typing

import pydantic


class FrameworkConfig(pydantic.BaseModel):
    """Base class for framework config models."""

    @pydantic.model_validator(mode="before")
    @classmethod
    def secret_key_id(cls, data: dict[str, str | int | bool | dict[str, str] | None]) -> dict:
        """Read the *-secret-key-id style configuration.

        Args:
            data: model input.

        Returns:
            modified input with *-secret-key replaced by the secret content of *-secret-key-id.

        Raises:
            ValueError: if the *-secret-key-id is invalid.
            NotImplementedError: ill-formed subclasses.
        """
        secret_key_field = "secret_key"
        if secret_key_field not in cls.model_fields:
            secret_key_field = "app_secret_key"
        secret_key_config_name = cls.model_fields[secret_key_field].alias
        if not secret_key_config_name:
            raise NotImplementedError("framework configuration secret_key field has no alias")
        secret_key_id_config_name = f"{secret_key_config_name}-id"
        if data.get(secret_key_id_config_name):
            if data.get(secret_key_config_name):
                raise ValueError(
                    f"{secret_key_id_config_name} and {secret_key_config_name} "
                    "are defined in the same time"
                )
            secret_value = typing.cast(dict[str, str], data[secret_key_id_config_name])
            if "value" not in secret_value:
                raise ValueError(
                    f"{secret_key_id_config_name} missing 'value' key in the secret content"
                )
            if len(secret_value) > 1:
                raise ValueError(f"{secret_key_id_config_name} secret contains multiple values")
            data[secret_key_config_name] = secret_value["value"]
        return data
