"""Seed the local S3 (RustFS) bucket with the Week 2 source files.

Creates the bucket from S3_BUCKET (if it doesn't exist) and uploads the two
files produced by ``generate_data.py``. Safe to re-run.

Prereqs:
  1. docker compose up -d            (RustFS must be running)
  2. uv run python scripts/generate_data.py

Then:
  uv run python scripts/seed_s3.py
"""

from __future__ import annotations

from pathlib import Path

from botocore.exceptions import ClientError

from de_pipeline.config import get_s3_client, settings

SOURCE_DIR = Path("data/source")


def ensure_bucket(client, bucket: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
        print(f"bucket '{bucket}' already exists")
    except ClientError:
        client.create_bucket(Bucket=bucket)
        print(f"created bucket '{bucket}'")


def upload(client, bucket: str, local_path: Path, key: str) -> None:
    if not local_path.exists():
        raise FileNotFoundError(
            f"{local_path} not found — run `uv run python scripts/generate_data.py` first"
        )
    client.upload_file(str(local_path), bucket, key)
    size = local_path.stat().st_size
    print(f"uploaded {local_path} -> s3://{bucket}/{key} ({size:,} bytes)")


def main() -> None:
    client = get_s3_client()
    ensure_bucket(client, settings.bucket)
    upload(client, settings.bucket, SOURCE_DIR / "orders.csv", settings.orders_key)
    upload(client, settings.bucket, SOURCE_DIR / "customers.json", settings.customers_key)
    print(f"\ndone. endpoint={settings.endpoint_url} bucket={settings.bucket}")


if __name__ == "__main__":
    main()
