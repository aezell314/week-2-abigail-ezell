-- Day 2: move your dedupe_orders() SQL here.
--
-- Build orders_deduped: exactly one row per order_id — the newest copy by
-- updated_at — keeping all the original columns. Use a CTE with
-- ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC).
--
-- Until you fill this in, the file is a harmless placeholder.
SELECT 'TODO: orders_deduped.sql not written yet' AS todo;
