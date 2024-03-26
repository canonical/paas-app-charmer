# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the SecretStorage for managing the persistent secret storage for the charm."""
import secrets

import ops

import paas_app_charmer.secret_storage


class GunicornSecretStorage(paas_app_charmer.secret_storage.SecretStorage):
    """A class that manages secret keys required by the WSGI charms."""

    def gen_initial_value(self) -> dict[str, str]:
        """Generate the initial secret values.

        Returns:
            The initial secret values.
        """
        return {self._key: secrets.token_urlsafe(64)}

    def __init__(self, charm: ops.CharmBase, key: str):
        """Initialize the SecretStorage with a given charm object.

        Args:
            charm: The charm object that uses the SecretStorage.
            key: The secret key name stored in the relation data.
        """
        super().__init__(charm=charm, keys=[key])
        self._key = key

    def get_secret_key(self) -> str:
        """Retrieve the application secret key from the peer relation data.

        Returns:
            The application secret key.
        """
        return self.get_secret(self._key)

    def reset_secret_key(self) -> None:
        """Generate a new application secret key and store it within the peer relation data."""
        self.set_secret(self._key, secrets.token_urlsafe(32))
