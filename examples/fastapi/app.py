# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}
