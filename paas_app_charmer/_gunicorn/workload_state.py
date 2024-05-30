# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


import pathlib


class WorkloadState:
    """TODO.

    In search for a better name and place, just testing ideas.
    TODO PUT THIS IN WEBSERVER CONFIG BETTER?

    Attrs:
        user: The UNIX user name for running the service.
        group: The UNIX group name for running the service.
        app_dir: The WSGI application directory in the WSGI application container.
        application_log_file: the file path for the WSGI application access log.
        application_error_log_file: the file path for the WSGI application error log.
        base_dir: The project base directory in the WSGI application container.
    """

    statsd_host = "localhost:9125"
    port = 8000
    user = "_daemon_"
    group = "_daemon_"

    def __init__(self, framework: str):
        self.framework = framework
        self.container_name = f"{self.framework}-app"
        self.base_dir = pathlib.Path(f"/{framework}")
        self.application_log_file = pathlib.Path(f"/var/log/{self.framework}/access.log")
        self.application_error_log_file = pathlib.Path(f"/var/log/{self.framework}/error.log")
        self.base_dir = pathlib.Path(f"/{framework}")
        self.app_dir = self.base_dir / "app"
        self.state_dir = self.base_dir / "state"
        self.service_name = self.framework

    @property
    def log_files(self):
        return [
            self.application_log_file,
            self.application_error_log_file,
        ]
