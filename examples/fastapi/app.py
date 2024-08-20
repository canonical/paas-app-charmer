# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import os

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return "Hello, World!"


@app.get("/env/user-defined-config")
async def user_defined_config():
    return os.getenv("APP_USER_DEFINED_CONFIG", None)


@app.get("/json")
async def json():
    return {"message": "Hello World"}
