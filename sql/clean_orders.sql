-- Day 2: move your clean_orders() SQL here.
--
-- Build clean_orders FROM orders_deduped:
--   * cast price text ("$1,209.50", "  42.99 ") to a number — strip $, comma, spaces
--   * cast quantity to an integer
--   * DROP rows missing a usable quantity or price
--   * normalize status: lower-case, trimmed, blanks -> 'unknown'
--   * parse order_date into a real DATE (Day 3: handle all three formats)
--   * add line_total = quantity * price
--
CREATE OR REPLACE TABLE clean_orders AS
    SELECT order_id,
    customer_id,
    sku,
    quantity::integer as quantity,
    regexp_replace(trim(price), '[$|,]', '', 'g')::double as price,
    coalesce(trim(lower(status)), 'unknown') as status,
    COALESCE(
        TRY_STRPTIME(order_date, '%d-%b-%Y'),
        TRY_STRPTIME(order_date, '%Y-%m-%d'),
        TRY_STRPTIME(order_date, '%m/%d/%Y')
    )::date as order_date,
    quantity::integer*regexp_replace(trim(price), '[$|,]', '', 'g')::double as line_total
    FROM orders_deduped
    where quantity is not null and price is not null;
