-- Day 2: move your dedupe_orders() SQL here.
--
-- Build orders_deduped: exactly one row per order_id — the newest copy by
-- updated_at — keeping all the original columns. Use a CTE with
-- ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC).
--
CREATE OR REPLACE TABLE orders_deduped AS
    WITH orders_ranked AS (
        SELECT *,
            ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC) AS rownum
        FROM raw_orders
    )
    SELECT * EXCLUDE (rownum, updated_at)
    FROM orders_ranked
    WHERE rownum = 1;
