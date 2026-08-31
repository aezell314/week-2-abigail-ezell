"""Shared pytest fixtures.

These build tiny local fixtures so the load/transform tests run WITHOUT needing
S3 or the full dataset. They mirror the shape of the real Week 2 source files,
including every kind of mess the transforms have to survive.

The sample is small but deliberately complete. Trace it once and the expected
numbers in the tests make sense:

  orders (9 raw rows -> 7 distinct order_ids):
    id 1  cust 1   appears TWICE (pending @01-05, then completed @01-06)  <- dedup
    id 2  cust 1   ISO date "2024-02-11"
    id 3  cust 2   price "$1,009.99" (comma), slash date "03/02/2024"
    id 4  cust 2   blank quantity                                          <- dropped
    id 5  cust 3   blank price                                             <- dropped
    id 6  (none)   NULL customer_id, appears TWICE                         <- dedup + NULL trap
    id 7  cust 3   blank status -> 'unknown'

  customers (4 raw rows -> 3 distinct customer_ids):
    cust 1   tags [vip, newsletter]
    cust 2   record_version 1   tags [new]
    cust 2   record_version 2   tags [new, vip]   <- newer, wins on dedup
    cust 3   tags []            (no tags)

  After dedup + clean, the 5 usable orders are ids 1,2,3,6,7. Order 6 has a NULL
  customer_id, so it survives clean_orders but is dropped by the customer join —
  that's the NULL trap the Day-3 reconciliation test checks.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

# 9 raw order rows. Note the duplicate ids (1 and 6), the blank quantity/price
# (4 and 5), the NULL customer_id (6), the three date formats, the money-as-text
# prices, and the messy / blank statuses.
SAMPLE_ORDERS_CSV = (
    "order_id,customer_id,sku,quantity,price,status,order_date,updated_at\n"
    "1,1,WIDGET-01,2,$12.50,pending,05-Jan-2024,2024-01-05 10:00:00\n"
    "1,1,WIDGET-01,2,$12.50,completed,05-Jan-2024,2024-01-06 09:00:00\n"
    "2,1,GADGET-07,1,$42.99,Completed,2024-02-11,2024-02-11 08:00:00\n"
    '3,2,CABLE-USB,3,"$1,009.99",SHIPPED,03/02/2024,2024-03-02 12:00:00\n'
    "4,2,WIDGET-02,,18.00, Pending ,20-Mar-2024,2024-03-20 07:00:00\n"
    "5,3,MOUNT-PRO,1,,shipped,01-Apr-2024,2024-04-01 07:00:00\n"
    "6,,SPROCKET-3,2,$99.00,cancelled,15-May-2024,2024-05-15 07:00:00\n"
    "6,,SPROCKET-3,2,$99.00,completed,15-May-2024,2024-05-16 07:00:00\n"
    "7,3,GADGET-12,4,$7.25,,2024-06-01,2024-06-01 07:00:00\n"
)

# 4 raw customer rows -> 3 distinct. customer 2 appears twice; record_version 2
# is the newer one (its tags add "vip"). zips are sometimes null.
SAMPLE_CUSTOMERS = [
    {
        "customer_id": 1,
        "name": "Ava Reyes",
        "email": "user1@example.com",
        "signup_date": "2023-04-10",
        "record_version": 1,
        "address": {"city": "Nashville", "state": "TN", "zip": "37206"},
        "tags": ["vip", "newsletter"],
    },
    {
        "customer_id": 2,
        "name": "Liam Tran",
        "email": "user2@example.com",
        "signup_date": "2023-09-01",
        "record_version": 1,
        "address": {"city": "Austin", "state": "TX", "zip": "78704"},
        "tags": ["new"],
    },
    {
        "customer_id": 2,
        "name": "Liam Tran",
        "email": "user2@example.com",
        "signup_date": "2023-09-01",
        "record_version": 2,
        "address": {"city": "Austin", "state": "TX", "zip": None},
        "tags": ["new", "vip"],
    },
    {
        "customer_id": 3,
        "name": "Maya Patel",
        "email": "user3@example.com",
        "signup_date": "2024-01-15",
        "record_version": 1,
        "address": {"city": "Denver", "state": "CO", "zip": None},
        "tags": [],
    },
]


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    """A temp directory holding tiny orders.csv + customers.json fixtures."""
    (tmp_path / "orders.csv").write_text(SAMPLE_ORDERS_CSV)
    (tmp_path / "customers.json").write_text(json.dumps(SAMPLE_CUSTOMERS, indent=2))
    return tmp_path


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB connection."""
    connection = duckdb.connect(":memory:")
    yield connection
    connection.close()


@pytest.fixture
def loaded_con(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> duckdb.DuckDBPyConnection:
    """A DuckDB connection with raw_orders + raw_customers already populated,
    mess and all. Lets the transform tests run without finishing load.py.

    Prices stay text (the column has "$"), order_date stays text (mixed formats),
    and the duplicate rows are present — exactly like the real raw load.
    """
    con.execute(
        "CREATE TABLE raw_orders AS SELECT * FROM read_csv_auto(?)",
        [str(raw_dir / "orders.csv")],
    )
    con.execute(
        "CREATE TABLE raw_customers AS SELECT * FROM read_json_auto(?)",
        [str(raw_dir / "customers.json")],
    )
    return con


@pytest.fixture
def transformed_con(loaded_con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """raw tables loaded AND the prerequisite transforms run, so tag_revenue /
    reconciliation tests have clean_orders + customer_order_summary to build on.

    Imported lazily so this module still imports before transform.py is written.
    """
    from de_pipeline import transform

    transform.dedupe_orders(loaded_con)
    transform.clean_orders(loaded_con)
    transform.customer_order_summary(loaded_con)
    return loaded_con
