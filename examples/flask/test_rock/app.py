# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import time
import urllib.parse
from urllib.parse import urlparse

import boto3
import botocore.config
import psycopg
import pymongo
import pymongo.database
import pymongo.errors
import pymysql
import pymysql.cursors
import redis
from flask import Flask, g, jsonify, request

app = Flask(__name__)
app.config.from_prefixed_env()


def get_mysql_database():
    """Get the mysql db connection."""
    if "mysql_db" not in g:
        if "MYSQL_DB_CONNECT_STRING" in os.environ:
            uri_parts = urlparse(os.environ["MYSQL_DB_CONNECT_STRING"])
            g.mysql_db = pymysql.connect(
                host=uri_parts.hostname,
                user=uri_parts.username,
                password=uri_parts.password,
                database=uri_parts.path[1:],
                port=uri_parts.port,
            )
        else:
            return None
    return g.mysql_db


def get_postgresql_database():
    """Get the postgresql db connection."""
    if "postgresql_db" not in g:
        if "POSTGRESQL_DB_CONNECT_STRING" in os.environ:
            g.postgresql_db = psycopg.connect(
                conninfo=os.environ["POSTGRESQL_DB_CONNECT_STRING"],
            )
        else:
            return None
    return g.postgresql_db


def get_mongodb_database() -> pymongo.database.Database | None:
    """Get the mongodb db connection."""
    if "mongodb_db" not in g:
        if "MONGODB_DB_CONNECT_STRING" in os.environ:
            uri = os.environ["MONGODB_DB_CONNECT_STRING"]
            client = pymongo.MongoClient(uri)
            db = urllib.parse.urlparse(uri).path.removeprefix("/")
            g.mongodb_db = client.get_database(db)
        else:
            return None
    return g.mongodb_db


def get_redis_database() -> redis.Redis | None:
    if "redis_db" not in g:
        if "REDIS_DB_CONNECT_STRING" in os.environ:
            uri = os.environ["REDIS_DB_CONNECT_STRING"]
            g.redis_db = redis.Redis.from_url(uri)
        else:
            return None
    return g.redis_db


def get_boto3_client():
    if "boto3_client" not in g:
        if "S3_ACCESS_KEY" in os.environ:
            s3_client_config = botocore.config.Config(
                s3={
                    "addressing_style": os.environ["S3_ADDRESSING_STYLE"],
                },
                # no_proxy env variable is not read by boto3, so
                # this is needed for the tests to avoid hitting the proxy.
                proxies={},
            )
            g.boto3_client = boto3.client(
                "s3",
                os.environ["S3_REGION"],
                aws_access_key_id=os.environ["S3_ACCESS_KEY"],
                aws_secret_access_key=os.environ["S3_SECRET_KEY"],
                endpoint_url=os.environ["S3_ENDPOINT"],
                use_ssl=False,
                config=s3_client_config,
            )
        else:
            return None
    return g.boto3_client


@app.teardown_appcontext
def teardown_database(_):
    """Tear down databases connections."""
    mysql_db = g.pop("mysql_db", None)
    if mysql_db is not None:
        mysql_db.close()
    postgresql_db = g.pop("postgresql_db", None)
    if postgresql_db is not None:
        postgresql_db.close()
    mongodb_db = g.pop("mongodb_db", None)
    if mongodb_db is not None:
        mongodb_db.client.close()
    boto3_client = g.pop("boto3_client", None)
    if boto3_client is not None:
        boto3_client.close()


@app.route("/")
def hello_world():
    return "Hello, World!"


@app.route("/sleep")
def sleep():
    duration_seconds = int(request.args.get("duration"))
    time.sleep(duration_seconds)
    return ""


@app.route("/config/<config_name>")
def config(config_name: str):
    return jsonify(app.config.get(config_name))


@app.route("/mysql/status")
def mysql_status():
    """Mysql status endpoint."""
    if database := get_mysql_database():
        with database.cursor() as cursor:
            sql = "SELECT version()"
            cursor.execute(sql)
            cursor.fetchone()
            return "SUCCESS"
    return "FAIL"


@app.route("/s3/status")
def s3_status():
    """S3 status endpoint."""
    if client := get_boto3_client():
        bucket_name = os.environ["S3_BUCKET"]
        objectsresponse = client.list_objects(Bucket=bucket_name)
        return "SUCCESS"
    return "FAIL"


@app.route("/postgresql/status")
def postgresql_status():
    """Postgresql status endpoint."""
    if database := get_postgresql_database():
        with database.cursor() as cursor:
            sql = "SELECT version()"
            cursor.execute(sql)
            cursor.fetchone()
            return "SUCCESS"
    return "FAIL"


@app.route("/mongodb/status")
def mongodb_status():
    """Mongodb status endpoint."""
    if (database := get_mongodb_database()) is not None:
        database.list_collection_names()
        return "SUCCESS"
    return "FAIL"


@app.route("/redis/status")
def redis_status():
    """Mongodb status endpoint."""
    if database := get_redis_database():
        try:
            database.set("foo", "bar")
            return "SUCCESS"
        except pymongo.errors.PyMongoError:
            pass
    return "FAIL"


@app.route("/env")
def get_env():
    """Return environment variables"""
    return jsonify(dict(os.environ))
