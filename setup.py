# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import pathlib

from setuptools import setup

requirements_txt = pathlib.Path(__file__).parent / "requirements.txt"
requirements = requirements_txt.read_text(encoding="utf-8").splitlines()

setup(
    name="paas-app-charmer",
    version="0.2.0",
    description="Companion library for 12-factor charms",
    url="https://github.com/canonical/paas-app-charmer",
    author="Canonical IS DevOps team",
    author_email="is-devops-team@canonical.com",
    install_requires=requirements,
    package_data={"paas_app_charmer": ["**/cos/**", "**/cos/**/.**"]},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
    ],
    python_requires=">=3.10",
)
