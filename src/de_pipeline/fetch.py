"""Day 1 warm-up — fetch the raw source files from S3 (RustFS).

You did this in Week 1; do it again from muscle memory to get the data flowing,
then move on to the real work (transform.py). The two source objects
(``orders.csv`` and ``customers.json``) live in the S3 bucket. Download them into
a local ``data/raw/`` folder so the later stages can read them.

``config.py`` is provided for you. It gives you ``get_s3_client()`` — a
ready-to-use boto3 S3 client already pointed at the local store — and
``settings`` (bucket name + the two object keys). You write everything else.

Docs:
  - boto3 S3 client:     https://docs.aws.amazon.com/boto3/latest/reference/services/s3.html
  - downloading a file:  https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/download_file.html
"""

from __future__ import annotations

from pathlib import Path

from de_pipeline.config import settings

# Where downloaded raw files land. (data/ is git-ignored.)
RAW_DIR = Path("data/raw")


def fetch_object(key: str, dest_dir: Path = RAW_DIR) -> Path:
    """Download the object ``key`` from the bucket into ``dest_dir``, and return
    the local path it was written to."""
    raise NotImplementedError("Day 1: implement fetch_object()")


def fetch_all(dest_dir: Path = RAW_DIR) -> dict[str, Path]:
    """Download both source files and return a mapping of name -> local path:
    ``{"orders": <path>, "customers": <path>}``.

    (The object keys to download are ``settings.orders_key`` and
    ``settings.customers_key``.)"""
    raise NotImplementedError("Day 1: implement fetch_all()")


if __name__ == "__main__":
    # Quick manual check:  uv run python -m de_pipeline.fetch
    paths = fetch_all()
    for name, path in paths.items():
        print(f"fetched {name} -> {path} ({path.stat().st_size:,} bytes)")
    print(f"bucket={settings.bucket} endpoint={settings.endpoint_url}")
