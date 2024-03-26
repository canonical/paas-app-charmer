#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Django Charm service."""
import itertools
import logging
import pathlib
import secrets
import typing

import ops

# pydantic is causing this no-name-in-module problem
from pydantic import BaseModel, Extra, Field, ValidationError  # pylint: disable=no-name-in-module

from paas_app_charmer._gunicorn.charm import GunicornBase
from paas_app_charmer.exceptions import CharmConfigInvalidError

logger = logging.getLogger(__name__)


class DjangoConfig(BaseModel, extra=Extra.allow):  # pylint: disable=too-few-public-methods
    """Represent Django builtin configuration values.

    Attrs:
        debug: whether Django debug mode is enabled.
        secret_key: a secret key that will be used for security related needs by your
            Django application.
        allowed_hosts: a list of host/domain names that this Django site can serve.
    """

    debug: bool | None = Field(default=None)
    secret_key: str | None = Field(default=None, min_length=1)
    allowed_hosts: list[str]


class Charm(GunicornBase):  # pylint: disable=too-many-instance-attributes
    """Django Charm service."""

    def __init__(self, framework: ops.Framework) -> None:
        """Initialize the Django charm.

        Args:
            framework: operator framework.
        """
        super().__init__(framework=framework, wsgi_framework="django")
        self.framework.observe(self.on.django_app_pebble_ready, self._on_django_app_pebble_ready)
        self.framework.observe(self.on.create_superuser_action, self._on_create_superuser_action)

    def get_wsgi_config(self) -> BaseModel:
        """Return Django framework related configurations.

        Returns:
             Flask framework related configurations.

        Raises:
            CharmConfigInvalidError: if charm config is not valid.
        """
        django_config: dict[str, typing.Any] = {
            "debug": self.config.get("django-debug"),
            "secret_key": self.config.get("django-secret-key"),
        }
        allowed_hosts = self.config.get("django-allowed-hosts", "")
        if allowed_hosts.strip():
            django_config["allowed_hosts"] = [h.strip() for h in allowed_hosts.split(",")]
        else:
            django_config["allowed_hosts"] = []
        try:
            return DjangoConfig.model_validate(django_config)
        except ValidationError as exc:
            error_fields = set(
                itertools.chain.from_iterable(error["loc"] for error in exc.errors())
            )
            error_field_str = " ".join(f"django-{f}".replace("_", "-") for f in error_fields)
            raise CharmConfigInvalidError(f"invalid configuration: {error_field_str}") from exc

    def get_cos_dir(self) -> str:
        """Return the directory with COS related files.

        Returns:
            Return the directory with COS related files.
        """
        return str((pathlib.Path(__file__).parent / "cos").absolute())

    def _on_django_app_pebble_ready(self, _: ops.PebbleReadyEvent) -> None:
        """Handle the pebble-ready event."""
        self.restart()

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
                ["python", "manage.py", "createsuperuser", "--noinput"],
                environment={
                    "DJANGO_SUPERUSER_PASSWORD": password,
                    "DJANGO_SUPERUSER_USERNAME": event.params["username"],
                    "DJANGO_SUPERUSER_EMAIL": event.params["email"],
                    **self._wsgi_app.gen_environment(),
                },
                combine_stderr=True,
                working_dir=str(self._charm_state.app_dir),
            ).wait_output()
            event.set_results({"password": password})
        except ops.pebble.ExecError as e:
            event.fail(str(e.stdout))
