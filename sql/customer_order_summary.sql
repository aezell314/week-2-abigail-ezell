-- Day 2: move your customer_order_summary() SQL here.
--
-- One row per customer: customer_id, name, order_count, total_revenue.
--   * dedup raw_customers first (keep the highest record_version) — a CTE works
--   * join clean_orders to the deduped customers
--   * GROUP BY customer; count orders, sum line_total
--   * keep only customers with at least $min_orders orders (a BOUND parameter)
--
-- Run it with:  con.execute(read_sql("customer_order_summary"), {"min_orders": n})
--
CREATE OR REPLACE TABLE customer_order_summary AS
    WITH customers_cleaned AS (         
        SELECT customer_id,                 
            name,                 
            email,                 
            signup_date,                 
            record_version,                 
            address,                 
            tags
        FROM (
            SELECT *,
                ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY record_version DESC) AS rownum         
            FROM raw_customers
        )
        WHERE rownum = 1 -- Filters customers BEFORE the join
    ),  
    orders_cleaned as (
        select order_id,
        coalesce(customer_id, 0) as customer_id,
        sku,
        quantity,
        price,
        status,
        order_date,
        line_total
        from clean_orders
    )
    SELECT o.customer_id,
        c.name,
        count(o.order_id) as order_count,
        sum(o.line_total) as total_revenue
    FROM customers_cleaned c
    right join orders_cleaned o
    using(customer_id)
    group by all
    having count(o.order_id) >= $min_orders
    ;
