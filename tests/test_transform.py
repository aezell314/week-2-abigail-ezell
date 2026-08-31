"""Transform tests — the heart of Week 2. No S3 required.

These use the ``loaded_con`` / ``transformed_con`` fixtures (see conftest.py),
which populate raw_orders + raw_customers from the small sample, so they pass as
soon as your transforms work — even before load.py is finished.

The tests are grouped by the day they become your checkpoint. Earlier days'
tests should stay green as you go; later days start red and you turn them green.
Trace the sample in conftest.py once and every number below will make sense.
"""

from __future__ import annotations

import duckdb

from de_pipeline import transform

# --------------------------------------------------------------------------- #
# Day 1 — dedup, clean, summarize with real SQL (CTEs + ROW_NUMBER)
# --------------------------------------------------------------------------- #


def test_dedupe_orders_keeps_latest_per_order_id(loaded_con: duckdb.DuckDBPyConnection) -> None:
    rows = transform.dedupe_orders(loaded_con)
    assert rows == 7  # 9 raw rows -> 7 distinct order_ids

    # Exactly one row per order_id now.
    dupes = loaded_con.execute(
        "SELECT order_id, count(*) FROM orders_deduped GROUP BY order_id HAVING count(*) > 1"
    ).fetchall()
    assert dupes == []

    # The NEWEST copy won: order 1's later row was 'completed' (updated 2024-01-06),
    # order 6's later row was also 'completed' (updated 2024-05-16). (Still raw,
    # un-normalized status here — normalizing is clean_orders' job.)
    status1 = loaded_con.execute(
        "SELECT status FROM orders_deduped WHERE order_id = 1"
    ).fetchone()[0]
    status6 = loaded_con.execute(
        "SELECT status FROM orders_deduped WHERE order_id = 6"
    ).fetchone()[0]
    assert status1 == "completed"
    assert status6 == "completed"


def test_clean_orders_casts_money_and_drops_unusable(
    loaded_con: duckdb.DuckDBPyConnection,
) -> None:
    transform.dedupe_orders(loaded_con)
    rows = transform.clean_orders(loaded_con)
    # From the 7 deduped orders, ids 4 (blank quantity) and 5 (blank price) drop.
    assert rows == 5

    # order_date is now a real DATE, not text.
    dtype = loaded_con.execute(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = 'clean_orders' AND column_name = 'order_date'"
    ).fetchone()[0]
    assert "DATE" in dtype.upper()

    # status is normalized: trimmed, lower-cased, blanks -> 'unknown'.
    statuses = {
        r[0] for r in loaded_con.execute("SELECT DISTINCT status FROM clean_orders").fetchall()
    }
    assert statuses == {"completed", "shipped", "unknown"}

    # The money-as-text price parsed correctly, comma and all:
    # order 3 was "$1,009.99" x quantity 3  ->  line_total 3029.97.
    line_total_3 = loaded_con.execute(
        "SELECT line_total FROM clean_orders WHERE order_id = 3"
    ).fetchone()[0]
    assert round(float(line_total_3), 2) == 3029.97


def test_customer_order_summary_is_one_row_per_customer(
    loaded_con: duckdb.DuckDBPyConnection,
) -> None:
    transform.dedupe_orders(loaded_con)
    transform.clean_orders(loaded_con)
    rows = transform.customer_order_summary(loaded_con)
    # Customers 1, 2, 3 have orders. (Order 6 has a NULL customer_id, so it has
    # no one to attribute to — that's the Day-3 NULL trap, tested separately.)
    assert rows == 3

    # No customer appears twice.
    dupes = loaded_con.execute(
        "SELECT customer_id, count(*) FROM customer_order_summary "
        "GROUP BY customer_id HAVING count(*) > 1"
    ).fetchall()
    assert dupes == []

    # Customer 2 is in raw_customers TWICE (record_version 1 and 2). If you didn't
    # dedup customers before joining, their single order (id 3) gets counted twice.
    order_count_2 = loaded_con.execute(
        "SELECT order_count FROM customer_order_summary WHERE customer_id = 2"
    ).fetchone()[0]
    assert order_count_2 == 1

    # Customer 1 placed two orders (ids 1 and 2).
    order_count_1 = loaded_con.execute(
        "SELECT order_count FROM customer_order_summary WHERE customer_id = 1"
    ).fetchone()[0]
    assert order_count_1 == 2


# --------------------------------------------------------------------------- #
# Day 2 — SQL in files + parameter binding, and one transform in Polars
# --------------------------------------------------------------------------- #


def test_customer_order_summary_min_orders_is_a_bound_param(
    loaded_con: duckdb.DuckDBPyConnection,
) -> None:
    transform.dedupe_orders(loaded_con)
    transform.clean_orders(loaded_con)
    # Only customers with >= 2 orders. Just customer 1 qualifies. The threshold
    # must reach the SQL as a BOUND parameter ($min_orders), not an f-string.
    rows = transform.customer_order_summary(loaded_con, min_orders=2)
    assert rows == 1
    only_id = loaded_con.execute("SELECT customer_id FROM customer_order_summary").fetchone()[0]
    assert only_id == 1


def test_tag_revenue_explodes_tags_in_polars(
    transformed_con: duckdb.DuckDBPyConnection,
) -> None:
    # transformed_con has dedupe -> clean -> summary already run.
    rows = transform.tag_revenue(transformed_con)
    # Distinct tags across deduped customers WITH orders: vip, newsletter, new.
    # (Customer 3 has no tags; customer 2's winning record adds 'vip'.)
    assert rows == 3

    tags = {r[0] for r in transformed_con.execute("SELECT tag FROM tag_revenue").fetchall()}
    assert tags == {"vip", "newsletter", "new"}

    # 'vip' belongs to customers 1 (revenue 67.99) and 2 (revenue 3029.97).
    vip_revenue = transformed_con.execute(
        "SELECT revenue FROM tag_revenue WHERE tag = 'vip'"
    ).fetchone()[0]
    assert round(float(vip_revenue), 2) == 3097.96


# --------------------------------------------------------------------------- #
# Day 3 — the hard parts: all three date formats, and the NULL-join trap
# --------------------------------------------------------------------------- #


def test_all_order_dates_parse_across_formats(loaded_con: duckdb.DuckDBPyConnection) -> None:
    transform.dedupe_orders(loaded_con)
    transform.clean_orders(loaded_con)
    # The 5 clean orders span all three date formats ("05-Jan-2024", "2024-02-11",
    # "03/02/2024"). A single strptime only catches one of them; the rest land
    # NULL. Parse all three (COALESCE over TRY_STRPTIME attempts) so none are NULL.
    null_dates = loaded_con.execute(
        "SELECT count(*) FROM clean_orders WHERE order_date IS NULL"
    ).fetchone()[0]
    assert null_dates == 0


def test_summary_handles_null_customer_trap(loaded_con: duckdb.DuckDBPyConnection) -> None:
    transform.dedupe_orders(loaded_con)
    transform.clean_orders(loaded_con)
    transform.customer_order_summary(loaded_con)

    total_summary = loaded_con.execute(
        "SELECT sum(total_revenue) FROM customer_order_summary"
    ).fetchone()[0]
    total_clean = loaded_con.execute("SELECT sum(line_total) FROM clean_orders").fetchone()[0]
    unassigned = loaded_con.execute(
        "SELECT sum(line_total) FROM clean_orders WHERE customer_id IS NULL"
    ).fetchone()[0]

    # Order 6 (NULL customer_id) is 2 * $99.00 = $198.00 of revenue with no one
    # to attribute it to.
    assert round(float(unassigned), 2) == 198.00

    # The reconciliation identity: attributed revenue + unassigned revenue equals
    # all clean revenue. If a dup customer double-counted, or an order silently
    # vanished, this fails.
    assert round(float(total_summary) + float(unassigned), 2) == round(float(total_clean), 2)


def test_run_transforms_returns_all_counts(loaded_con: duckdb.DuckDBPyConnection) -> None:
    result = transform.run_transforms(loaded_con)
    assert result == {
        "orders_deduped": 7,
        "clean_orders": 5,
        "customer_order_summary": 3,
        "tag_revenue": 3,
    }
