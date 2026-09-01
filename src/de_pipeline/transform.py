"""Days 1-3 — the real work: serious, DE-flavored SQL over a messy warehouse.

Week 1's transforms were one-liners. This week the raw tables fight back:

  raw_orders
    - duplicate ``order_id`` rows (re-ingested), each with a different
      ``updated_at`` -> you want exactly one row per order: the newest.
    - ``price`` is TEXT like "$1,209.50" / "  42.99 " / "" -> strip + cast.
    - ``order_date`` arrives in THREE formats -> parse them all to one DATE.
    - ``status`` has mixed case, stray spaces, and some blanks.
    - some rows have a blank ``customer_id`` (a NULL join key) or blank
      quantity/price (unusable -> drop).
  raw_customers
    - duplicate ``customer_id`` rows with different ``record_version`` -> dedup,
      or your per-customer order counts double (a JOIN fan-out trap).
    - a ``tags`` list per customer (semi-structured).

THE ARC OF THE WEEK
  Day 1  Write these transforms as embedded SQL right here, using CTEs and
         ROW_NUMBER() for the dedup. Get the tests green.
  Day 2  Refactor each transform's SQL out into a file under ``sql/`` and run it
         with ``read_sql()`` + DuckDB parameter binding (no f-string SQL!). Then
         do ONE transform — ``tag_revenue`` — in Polars instead of SQL, as a
         deliberate tool choice.
  Day 3  Handle the hard parts properly: all three date formats, the casting
         edge cases, and the INNER-JOIN "NULL trap".

Docs:
  - CTEs (WITH):        https://duckdb.org/docs/stable/sql/query_syntax/with
  - window functions:   https://duckdb.org/docs/stable/sql/functions/window_functions
  - date parsing:       https://duckdb.org/docs/stable/sql/functions/dateformat
  - TRY_CAST / casting: https://duckdb.org/docs/stable/sql/expressions/cast
  - DuckDB <-> Polars:  https://duckdb.org/docs/stable/guides/python/polars
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl

# Where the .sql files live (you start using these on Day 2).
SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


def read_sql(name: str) -> str:
    """Read ``sql/<name>.sql`` and return its text. Provided for you — use it on
    Day 2 when you move your SQL out of this file. Example:

        con.execute(read_sql("clean_orders"))
        con.execute(read_sql("customer_order_summary"), {"min_orders": 2})
    """
    return (SQL_DIR / f"{name}.sql").read_text()


def dedupe_orders(con: duckdb.DuckDBPyConnection) -> int:
    """Build an ``orders_deduped`` table with exactly one row per ``order_id`` —
    the newest copy, by ``updated_at`` — and return its row count.

    Keep all the original columns; don't clean anything yet (that's the next
    step)."""
    con.execute(read_sql("orders_deduped"))
    num_rows = con.execute("select count(*) from orders_deduped;").fetchone()[0]
    return num_rows


def clean_orders(con: duckdb.DuckDBPyConnection) -> int:
    """Build a ``clean_orders`` table from ``orders_deduped`` and return its row
    count. ``clean_orders`` should:

      - cast ``price`` from text to a real number (strip "$", thousands ",",
        and surrounding spaces first);
      - cast ``quantity`` to an integer;
      - DROP rows missing a usable quantity or price;
      - normalize ``status`` to lower-case, trimmed, with blanks -> 'unknown';
      - parse ``order_date`` into a real DATE (Day 1: get the common format
        working; Day 3: handle ALL THREE formats so none come out NULL);
      - add ``line_total`` = quantity * price.

    Build it from ``orders_deduped`` (run ``dedupe_orders`` first), not from
    ``raw_orders`` — you don't want to clean duplicate rows."""
    con.execute(read_sql("clean_orders"))
    num_rows = con.execute("select count(*) from clean_orders;").fetchone()[0]
    return num_rows


def customer_order_summary(con: duckdb.DuckDBPyConnection, min_orders: int = 1) -> int:
    """Build a ``customer_order_summary`` table — one row per customer with
    ``customer_id``, ``name``, ``order_count``, ``total_revenue`` — by joining
    ``clean_orders`` to a DEDUPED view of ``raw_customers``. Return its row count.

    Watch out for two traps:
      - raw_customers has duplicate ``customer_id`` rows; dedup it (keep the
        highest ``record_version``) BEFORE joining, or every order gets counted
        once per duplicate customer row.
      - ``min_orders`` is a threshold: only keep customers with at least that
        many orders. On Day 2, pass it into your SQL with PARAMETER BINDING
        (``con.execute(sql, {"min_orders": min_orders})``), not an f-string."""
    con.execute(read_sql("customer_order_summary"), {"min_orders": min_orders})
    num_rows = con.execute("select count(*) from customer_order_summary;").fetchone()[0]
    return num_rows


def tag_revenue(con: duckdb.DuckDBPyConnection) -> int:
    """Build a ``tag_revenue`` table — columns ``tag`` and ``revenue`` (total
    revenue from customers carrying that tag), one row per distinct tag — and
    return its row count. Run ``customer_order_summary`` first.

    DO THIS ONE IN POLARS, on purpose. Exploding a list column (``tags``) into
    one row per tag and grouping is the kind of reshaping that reads more
    naturally in a DataFrame than in SQL. Pull what you need out of DuckDB into
    Polars, do the dedup + explode + group-by + sum there, then write the result
    back as a DuckDB table. (This is the week's "Polars as a tool choice, not a
    replacement" moment.)
    """
    cust = con.execute("SELECT customer_id, record_version, tags FROM raw_customers").pl()
    rev  = con.execute("SELECT customer_id, total_revenue FROM customer_order_summary").pl()
    # dedup customers (keep highest record_version)
    dedup_cust = (
        cust.sort("record_version", descending=True)
        .unique(subset=["customer_id"], keep="first")
    )
    # explode tags, drop empty/null tags, join revenue, group by tag
    # sum -> DataFrame `out` with columns ["tag", "revenue"]
    out = (
        dedup_cust
        .explode("tags")
        .filter(pl.col("tags").is_not_null() & (pl.col("tags") != ""))
        .join(rev, on="customer_id", how="inner")
        .group_by("tags")
        .agg(pl.col("total_revenue").sum().alias("revenue"))
        .rename({"tags": "tag"})
    )
    con.execute("CREATE OR REPLACE TABLE tag_revenue AS SELECT * FROM out")
    num_rows = con.execute("select count(*) from tag_revenue;").fetchone()[0]
    return num_rows

def run_transforms(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Run every transform in order and return ``{table_name: row_count}``.

    Order matters: dedupe_orders -> clean_orders -> customer_order_summary ->
    tag_revenue."""
    deduporders = dedupe_orders(con)
    cleanorders = clean_orders(con)
    custordersum = customer_order_summary(con)
    tagrevenue = tag_revenue(con)
    return {
      'orders_deduped':deduporders,
      'clean_orders':cleanorders,
      'customer_order_summary':custordersum,
      'tag_revenue':tagrevenue
      }
