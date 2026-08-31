"""Day 1 tests — these talk to the real S3 (RustFS) store.

They are skipped automatically if RustFS isn't running, so the rest of the suite
still works. To run them: `docker compose up -d`, seed the data, then `uv run pytest`.
"""

from __future__ import annotations

from pathlib import Path

import boto3
import pytest
from botocore.config import Config

from de_pipeline import fetch
from de_pipeline.config import settings


def _s3_available() -> bool:
    # This runs at collection time on EVERY `pytest` run, including the no-S3
    # tests. Use a 1-second, single-attempt client so a down RustFS skips these
    # tests almost instantly instead of stalling the whole suite on retries.
    client = boto3.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key,
        aws_secret_access_key=settings.secret_key,
        region_name=settings.region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=1,
            read_timeout=1,
            retries={"max_attempts": 1},
        ),
    )
    try:
        client.head_bucket(Bucket=settings.bucket)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _s3_available(),
    reason="RustFS/bucket not reachable — run `docker compose up -d` and seed first",
)


def test_fetch_all_downloads_both_files(tmp_path: Path) -> None:
    paths = fetch.fetch_all(dest_dir=tmp_path)

    assert set(paths) == {"orders", "customers"}
    assert paths["orders"].exists()
    assert paths["customers"].exists()
    # The real orders file is large; a successful download is clearly non-trivial.
    assert paths["orders"].stat().st_size > 1000
