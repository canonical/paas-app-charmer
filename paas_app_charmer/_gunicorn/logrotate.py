#!/bin/python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Rotate Gunicorn logs.

It will be injected into the container and must not dependencies on non-standard libraries.
"""
import argparse
import datetime
import glob
import os
import subprocess  # nosec B404
import time

KEEP_ARCHIVES = 8
MAX_SIZE = 256 * 1024 * 1024


def rotate(filename: str) -> bool:
    """Rotate the current Gunicorn log file.

    Args:
        filename: the name of the log file.

    Returns:
        True if the log file was rotated, False otherwise.
    """
    if not os.path.isfile(filename) or os.stat(filename).st_size < MAX_SIZE:
        return False
    name, ext = os.path.splitext(filename)
    archive_name = f"{name}-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}{ext}"
    os.rename(filename, archive_name)
    pattern = f"{name}-*{ext}"
    files = sorted(glob.glob(pattern), reverse=True)
    for file in files[KEEP_ARCHIVES:]:
        os.remove(file)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rotate Gunicorn logs.")
    parser.add_argument(
        "--framework", required=True, help="The WSGI framework name (flask, django)."
    )
    args = parser.parse_args()
    framework = args.framework
    access_file = f"/var/log/{framework}/access.log"
    error_file = f"/var/log/{framework}/error.log"
    while True:
        time.sleep(60 * 3)
        # don't know why pylint think this is a constant
        rotated = rotate(access_file)  # pylint: disable=invalid-name
        rotated = rotate(error_file) or rotated  # pylint: disable=invalid-name
        if rotated:
            # pylint: disable=subprocess-run-check
            proc = subprocess.run(["/bin/pebble", "signal", "USR1", framework])  # nosec B603
            if proc.returncode != 0:
                print("gunicorn hasn't started")
