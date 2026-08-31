"""Day 1 warm-up — load the raw files into DuckDB.

Same shape as Week 1: open a DuckDB database (one file the whole pipeline shares)
and load each local raw file into its own table, AS-IS:
    data/raw/orders.csv      -> table ``raw_orders``
    data/raw/customers.json  -> table ``raw_customers``

Load it raw, mess and all — don't try to clean anything here. ``raw_orders`` will
have duplicate ``order_id`` rows, blank cells, money-as-text, and three date
formats; ``raw_customers`` will have duplicate ``customer_id`` rows and nested
nulls. That's expected. The cleaning is transform.py's job (the "T" in ELT).

Docs:
  - DuckDB Python API:   https://duckdb.org/docs/stable/clients/python/overview
  - reading CSV files:   https://duckdb.org/docs/stable/data/csv/overview
  - reading JSON files:  https://duckdb.org/docs/stable/data/json/overview
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from de_pipeline.fetch import RAW_DIR

# The DuckDB database file the whole pipeline shares.
DB_PATH = Path("data/warehouse.duckdb")


def connect(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    """Open (creating it if needed) the DuckDB database at ``db_path`` and return
    the connection."""
    raise NotImplementedError("Day 1: implement connect()")


def load_orders(con: duckdb.DuckDBPyConnection, raw_dir: Path = RAW_DIR) -> int:
    """Load ``raw_dir/orders.csv`` into a table named ``raw_orders``. Return the
    number of rows loaded.

    Tip: ``read_csv_auto`` is fine here. The price column is messy ("$1,209.50"),
    so DuckDB will land it as text on its own — don't fight that. You'll cast it
    deliberately in transform.py."""
    raise NotImplementedError("Day 1: implement load_orders()")


def load_customers(con: duckdb.DuckDBPyConnection, raw_dir: Path = RAW_DIR) -> int:
    """Load ``raw_dir/customers.json`` into a table named ``raw_customers``.
    Return the number of rows loaded."""
    raise NotImplementedError("Day 1: implement load_customers()")


def load_all(con: duckdb.DuckDBPyConnection, raw_dir: Path = RAW_DIR) -> dict[str, int]:
    """Load both files and return ``{table_name: row_count}`` — i.e.
    ``{"raw_orders": ..., "raw_customers": ...}``."""
    raise NotImplementedError("Day 1: implement load_all()")


if __name__ == "__main__":
    # uv run python -m de_pipeline.load
    con = connect()
    print("loaded:", load_all(con))
