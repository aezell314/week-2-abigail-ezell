# Week 2 — Your Transforms Are Basic. Let's Get Serious.

Last week you stood up a pipeline: S3 → DuckDB → a couple of one-line
transforms. It worked. This week the data fights back, and you answer it with
**real, DE-flavored SQL** — then you make a habit that separates data engineers
from people who just know SQL: **choosing the right tool for each transform.**

```
  S3 / RustFS         DuckDB            DuckDB (serious SQL)              Polars
 ┌────────────┐ fetch ┌──────────┐ dedup ┌───────────────┐ join+agg ┌──────────────┐
 │ orders.csv │ ────► │ raw_*    │ ────► │ orders_deduped│ ───────► │ tag_revenue  │
 │ customers… │       │ tables   │ clean │ clean_orders  │          │ (a DataFrame │
 └────────────┘       └──────────┘       │ customer_…    │          │  job, on     │
   (messier now)       (raw, as-is)      └───────────────┘          │  purpose)    │
                                          CTEs · ROW_NUMBER · casts  └──────────────┘
```

The data is messy the way real upstream feeds are messy:

- **Duplicate records.** The same `order_id` arrives more than once (a flaky
  re-ingestion). Each copy has an `updated_at` — keep the newest.
- **NULL join keys.** Some orders have no `customer_id`. They don't just
  disappear quietly — you have to *decide* what happens to them.
- **Money as text.** `price` shows up as `"$1,209.50"`, `"  42.99 "`, or blank.
- **Three date formats.** `order_date` is `05-Jan-2024` *or* `2024-01-05` *or*
  `01/05/2024`, row to row.
- **Duplicate customers too.** `customer_id` repeats with a higher
  `record_version`. Join carelessly and your order counts double.

## What's in this repo

| Path | What it is |
| --- | --- |
| `docker-compose.yml` | Local S3-compatible object store ([RustFS](https://rustfs.com)). |
| `scripts/generate_data.py` | Generates the messy source data. **Provided.** |
| `scripts/seed_s3.py` | Uploads it into the S3 bucket. **Provided.** |
| `src/de_pipeline/config.py` | S3 settings + client. **Provided — don't change.** |
| `src/de_pipeline/fetch.py` | **Day 1 warm-up** — download from S3 (like Week 1). |
| `src/de_pipeline/load.py` | **Day 1 warm-up** — load raw into DuckDB (like Week 1). |
| `src/de_pipeline/transform.py` | **Days 1–3, the real work** — dedup, clean, join. |
| `sql/` | **Day 2** — where your transform SQL moves into `.sql` files. |
| `tests/` | Tests that go green as you implement each stage. |

## One-time setup

You need [`uv`](https://docs.astral.sh/uv/) and Docker. Do these **in order** and
confirm each before moving on.

```bash
uv sync                                   # 1. create the environment (.venv/)
cp .env.example .env                      # 2. config (defaults already match)
docker compose up -d                      # 3. start RustFS (S3 on :9000, console :9001)
uv run python scripts/generate_data.py    # 4. generate the messy source data
uv run python scripts/seed_s3.py          # 5. upload it into the bucket
```

> _Confirm step 3:_ wait ~20–30s, then `docker compose ps` shows **healthy**.
> _Confirm step 4:_ it prints row counts and notes that row count > distinct
> count *on purpose* — that's the duplicate mess you'll dedup.
> _Confirm step 5:_ both files show up in the `raw` bucket at http://localhost:9001
> (login `rustfsadmin` / `rustfsadmin`).

### VS Code

Say yes to the recommended extensions (Python + **Ruff**). Ruff shows lint
inline (we don't auto-fix on save — fix the squiggles yourself). The **Testing**
panel (beaker icon) runs/debugs tests with a click.

## The week, day by day

**The rhythm: write a transform → run its test → get it green → move on.** Run
`uv run pytest` first to see the wall of red — that's your map. Turn it green one
checkpoint at a time.

> Day-1 tests start green-able; Day-3 tests (multi-format dates, the NULL trap)
> start red on purpose and you make them green by the end. A red later-day test
> isn't a bug in your earlier work — it's the next checkpoint.

### Day 1 — Real SQL + the mess (`fetch.py`, `load.py`, then `transform.py`)

Warm up by re-doing the Week 1 plumbing, then get into the SQL.

1. **Warm-up:** implement `fetch.py` then `load.py` (same as Week 1). Checkpoints:
   ```bash
   uv run pytest tests/test_load.py        # no S3 needed
   uv run pytest tests/test_fetch.py       # needs RustFS up + seeded
   ```
2. **Dedup with a window function.** Implement `dedupe_orders()` — one row per
   `order_id`, the newest by `updated_at`, using a CTE and
   `ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC)`.
   ```bash
   uv run pytest tests/test_transform.py::test_dedupe_orders_keeps_latest_per_order_id
   ```
3. **Clean it.** Implement `clean_orders()` — cast the money text to a number,
   normalize `status` (trim/lower, blanks → `unknown`), add `line_total`, drop
   rows with no usable quantity/price, and parse the *common* date format to get
   started.
   ```bash
   uv run pytest tests/test_transform.py::test_clean_orders_casts_money_and_drops_unusable
   ```
4. **Summarize.** Implement `customer_order_summary()` — one row per customer.
   Dedup `raw_customers` (highest `record_version`) **before** joining, or your
   counts double.
   ```bash
   uv run pytest tests/test_transform.py::test_customer_order_summary_is_one_row_per_customer
   ```

> **When is SQL the right tool?** For set-based work over tables — filtering,
> joining, aggregating, windowing — SQL is hard to beat and runs right where the
> data lives. Keep using it until it *stops* being the clearest option. You'll
> hit that point tomorrow.

### Day 2 — SQL in files + your first "not SQL" moment

1. **Move the SQL into files.** Refactor each transform's SQL out of
   `transform.py` into the matching file under `sql/`, and run it with the
   provided `read_sql()` helper (see `sql/README.md`). Your tests should stay
   green across the refactor — same SQL, just better organized.
2. **Bind parameters — don't f-string.** `customer_order_summary(min_orders=...)`
   must pass the threshold to SQL as a **bound parameter** (`$min_orders`):
   ```bash
   uv run pytest tests/test_transform.py::test_customer_order_summary_min_orders_is_a_bound_param
   ```
3. **One transform in Polars.** Implement `tag_revenue()` **in Polars**, not SQL.
   Exploding the `tags` list into one row per tag and summing revenue reads more
   naturally as a DataFrame op. This is *tool selection*, not replacement — you
   keep everything else in SQL.
   ```bash
   uv run pytest tests/test_transform.py::test_tag_revenue_explodes_tags_in_polars
   ```

> **The habit:** ask "what's the clearest, cheapest tool for *this* transform?"
> every time — not "which library is my favorite?" Most of this pipeline stays
> SQL. One piece is nicer in Polars. Noticing the difference is the skill.

### Day 3 — The hard parts

1. **Dates, all three formats.** Make `clean_orders` parse every `order_date`
   format so none come out NULL — `COALESCE` over a few `TRY_STRPTIME` attempts.
   ```bash
   uv run pytest tests/test_transform.py::test_all_order_dates_parse_across_formats
   ```
2. **The NULL-join trap.** Orders with a NULL `customer_id` quietly vanish from
   an inner join. Make the numbers reconcile (attributed + unassigned = all):
   ```bash
   uv run pytest tests/test_transform.py::test_summary_handles_null_customer_trap
   ```
3. **Wire it up.** Implement `run_transforms()`, then `main()` in `pipeline.py`.
   ```bash
   uv run pytest tests/test_transform.py::test_run_transforms_returns_all_counts
   ```
4. **Final checkpoint** — whole suite green (RustFS up + seeded), then the real
   run over the full dataset:
   ```bash
   uv run pytest
   uv run de-pipeline
   ```

## Working commands

```bash
uv run pytest                                       # whole suite
uv run pytest tests/test_transform.py               # one file
uv run pytest tests/test_transform.py::test_name    # one test (your checkpoints)
uv run ruff check .                                 # lint (same as VS Code inline)
```

## How you'll know you're done

`uv run pytest` is green with RustFS running and seeded, and `uv run de-pipeline`
runs end to end over the full data. The Day-1
`test_fetch.py` tests skip themselves when S3 isn't reachable — start RustFS and
seed if you want them to run.

## Troubleshooting

- **`docker compose ps` shows `unhealthy`/`starting`** — give it 20–30s; check
  `docker compose logs rustfs`.
- **Port 9000/9001 already in use** — often Week 1's RustFS still running. Stop
  it (`cd ../week-1 && docker compose down`) or change the left-hand port in
  `docker-compose.yml` and update `S3_ENDPOINT_URL` in `.env`.
- **`seed_s3.py` can't connect** — RustFS isn't up yet. Do setup step 3 first.
- **A money/date cast errors out** — prefer `TRY_CAST` / `TRY_STRPTIME` so a
  single bad value yields NULL instead of blowing up the whole query, then deal
  with the NULLs deliberately.
- **Windows** — use `copy .env.example .env`. If VS Code doesn't pick up the env,
  Command Palette → *Python: Select Interpreter* → the one under `.venv`.
