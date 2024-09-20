# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Django Charm service."""
import logging
import pathlib
import secrets
import typing

import ops
from pydantic import BaseModel, Extra, Field, model_validator, validator

from paas_app_charmer._gunicorn.charm import GunicornBase

logger = logging.getLogger(__name__)


class DjangoConfig(BaseModel, extra=Extra.ignore):
    """Represent Django builtin configuration values.

    Attrs:
        debug: whether Django debug mode is enabled.
        secret_key: a secret key that will be used for security related needs by your
            Django application.
        allowed_hosts: a list of host/domain names that this Django site can serve.
    """

    debug: bool | None = Field(alias="django-debug", default=None)
    secret_key: str | None = Field(alias="django-secret-key", default=None, min_length=1)
    allowed_hosts: str | None = Field(alias="django-allowed-hosts", default=[])

    @validator("allowed_hosts")
    @classmethod
    def allowed_hosts_to_list(cls, value: str | None) -> typing.List[str]:
        """Convert a comma separated list of allowed hosts to list.

        Args:
          value: allowed hosts as string.

        Return:
          list of allowed hosts.
        """
        if not value:
            return []
        return [h.strip() for h in value.split(",")]

    @model_validator(mode="before")
    @classmethod
    def secret_key_id(cls, data: dict[str, str | int | bool | dict[str, str] | None]) -> dict:
        """Read the new *-secret-key-id style configuration.

        Args:
            data: model input.

        Returns:
            modified input with *-secret-key replaced by the secret content of *-secret-key-id.

        Raises:
            ValueError: if the *-secret-key-id is invalid.
        """
        if "django-secret-key-id" in data and data["django-secret-key-id"]:
            secret_value = typing.cast(dict[str, str], data["django-secret-key-id"])
            if "value" not in secret_value:
                raise ValueError("django-secret-key-id missing 'value' key in the secret content")
            data["django-secret-key"] = secret_value["value"]
        return data


class Charm(GunicornBase):
    """Django Charm service.

    Attrs:
        framework_config_class: Base class for framework configuration.
    """

    framework_config_class = DjangoConfig

    def __init__(self, framework: ops.Framework) -> None:
        """Initialize the Django charm.

        Args:
            framework: operator framework.
        """
        super().__init__(framework=framework, framework_name="django")
        self.framework.observe(self.on.create_superuser_action, self._on_create_superuser_action)

    def get_cos_dir(self) -> str:
        """Return the directory with COS related files.

        Returns:
            Return the directory with COS related files.
        """
        return str((pathlib.Path(__file__).parent / "cos").absolute())

    def is_ready(self) -> bool:
        """Check if the charm is ready to start the workload application.

        For Django, at least one database is needed. Migrations will be run on startup
        and without that integration it will fail.

        Returns:
            True if the charm is ready to start the workload application.
        """
        if not super().is_ready():
            return False

        # At this point all integrations are correctly configured. If there is no database uri,
        # it means that there is no integration for databases or they are optional and no one
        # is set.
        charm_state = self._create_charm_state()
        if not charm_state.integrations.databases_uris:
            self.update_app_and_unit_status(
                ops.BlockedStatus("Django requires a database integration to work")
            )
            return False
        return True

    def _on_create_superuser_action(self, event: ops.ActionEvent) -> None:
        """Handle the create-superuser action.

        Args:
            event: the action event object.
        """
        if not self.is_ready():
            event.fail("django-app container is not ready")
        try:
            password = secrets.token_urlsafe(16)
            self._container.exec(
                ["python3", "manage.py", "createsuperuser", "--noinput"],
                environment={
                    "DJANGO_SUPERUSER_PASSWORD": password,
                    "DJANGO_SUPERUSER_USERNAME": event.params["username"],
                    "DJANGO_SUPERUSER_EMAIL": event.params["email"],
                    **self._gen_environment(),
                },
                combine_stderr=True,
                working_dir=str(self._workload_config.app_dir),
            ).wait_output()
            event.set_results({"password": password})
        except ops.pebble.ExecError as e:
            event.fail(str(e.stdout))
