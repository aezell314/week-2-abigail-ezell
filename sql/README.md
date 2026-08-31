# `sql/` — your transforms, as files (Day 2)

On **Day 1** you write your transform SQL as embedded strings inside
`transform.py`. That's fine to start, but real pipelines keep SQL in `.sql`
files: they're easier to read, diff, and review than Python strings, and your
editor highlights them.

On **Day 2** you move each transform's SQL into the matching file here, then run
it from Python with the provided helper:

```python
from de_pipeline.transform import read_sql

con.execute(read_sql("orders_deduped"))                       # no params
con.execute(read_sql("customer_order_summary"), {"min_orders": min_orders})  # bound param
```

## Parameter binding (do NOT f-string your SQL)

When a value comes from Python, pass it as a **bound parameter**, not by pasting
it into the SQL string. DuckDB supports named parameters with `$name`:

```sql
-- in customer_order_summary.sql
...
GROUP BY c.customer_id, c.name
HAVING count(*) >= $min_orders
```

```python
con.execute(read_sql("customer_order_summary"), {"min_orders": 2})
```

Binding keeps types correct and closes the door on SQL injection. Building SQL
with f-strings (`f"... >= {min_orders}"`) is the habit we're breaking here.

## The files

| File | Builds table | Notes |
| --- | --- | --- |
| `orders_deduped.sql` | `orders_deduped` | ROW_NUMBER() dedup, newest row per `order_id` |
| `clean_orders.sql` | `clean_orders` | cast money/quantity, parse dates, normalize status |
| `customer_order_summary.sql` | `customer_order_summary` | join + aggregate; uses `$min_orders` |

`tag_revenue` has no `.sql` file on purpose — that one you do in **Polars**.
