"""Central configuration, read from environment variables (or a local .env).

This module is provided for you — you should not need to change it. It loads
settings once and exposes them as a single ``settings`` object plus a helper
that hands you a ready-to-use S3 client pointed at the local RustFS store.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from dotenv import load_dotenv

# Load variables from a .env file in the project root, if present. Real
# environment variables always win over .env values.
load_dotenv()


@dataclass(frozen=True)
class Settings:
    endpoint_url: str
    access_key: str
    secret_key: str
    region: str
    bucket: str
    orders_key: str
    customers_key: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read settings from the environment once and cache them."""
    return Settings(
        endpoint_url=os.getenv("S3_ENDPOINT_URL", "http://localhost:9000"),
        access_key=os.getenv("S3_ACCESS_KEY", "rustfsadmin"),
        secret_key=os.getenv("S3_SECRET_KEY", "rustfsadmin"),
        region=os.getenv("S3_REGION", "us-east-1"),
        bucket=os.getenv("S3_BUCKET", "raw"),
        orders_key=os.getenv("ORDERS_KEY", "orders.csv"),
        customers_key=os.getenv("CUSTOMERS_KEY", "customers.json"),
    )


def get_s3_client() -> BaseClient:
    """Return a boto3 S3 client configured for the local RustFS endpoint.

    Because RustFS is not real AWS, we must pass the endpoint URL explicitly and
    use "path-style" addressing (bucket in the URL path, not the hostname).
    """
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.endpoint_url,
        aws_access_key_id=s.access_key,
        aws_secret_access_key=s.secret_key,
        region_name=s.region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            # Fail fast with a clear error if RustFS isn't running, instead of
            # hanging for ~30s on the default retry/backoff.
            connect_timeout=5,
            read_timeout=10,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


# Convenience singleton so callers can simply `from ... import settings`.
settings = get_settings()
