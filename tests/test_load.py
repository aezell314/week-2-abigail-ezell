"""Day 1 tests — load raw files into DuckDB. No S3 required (uses local fixtures).

The sample orders.csv has 9 rows (duplicates included — you load it raw, you
dedup later). The sample customers.json has 4 rows (customer 2 appears twice).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from de_pipeline import load


def test_load_orders_creates_table(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> None:
    count = load.load_orders(con, raw_dir=raw_dir)
    assert count == 9  # 9 raw rows, duplicates and all — don't dedup here
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    assert "raw_orders" in tables


def test_load_customers_creates_table(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> None:
    count = load.load_customers(con, raw_dir=raw_dir)
    assert count == 4  # 4 raw rows — customer 2 is in here twice
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    assert "raw_customers" in tables


def test_load_all_returns_counts(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> None:
    counts = load.load_all(con, raw_dir=raw_dir)
    assert counts == {"raw_orders": 9, "raw_customers": 4}
