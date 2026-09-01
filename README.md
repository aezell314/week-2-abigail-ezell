# Data Engineering Pipeline — DuckDB, S3, SQL, and Polars

This project implements an end-to-end data engineering pipeline for ingesting, cleaning, transforming, and aggregating messy order and customer data.

The pipeline uses an S3-compatible object store as its source, DuckDB for ingestion and SQL-based transformations, and Polars for a DataFrame-oriented aggregation. It is designed around realistic upstream data-quality problems including duplicate records, inconsistent date formats, malformed monetary values, NULL join keys, and versioned customer records.

## Pipeline Architecture

```text
 S3 / RustFS         DuckDB             DuckDB / SQL                  Polars
┌────────────┐      ┌──────────┐       ┌────────────────┐          ┌──────────────┐
│ orders.csv │ ───► │ raw_*    │ ────► │ orders_deduped │ ───────► │ tag_revenue  │
│ customers… │      │ tables   │       │ clean_orders   │          │              │
└────────────┘      └──────────┘       │ customer_*     │          │ DataFrame    │
                                       └────────────────┘          │ aggregation  │
                                        CTEs · ROW_NUMBER          └──────────────┘
                                        casts · joins · aggs
```

The implementation deliberately uses different transformation tools where they are most appropriate:

- **DuckDB SQL** handles set-oriented transformations such as filtering, deduplication, joins, cleaning, window functions, and aggregations.
- **Polars** handles tag-level revenue aggregation, where exploding nested tag values and grouping them is naturally expressed as DataFrame operations.

## Data Quality Challenges

The source data models several common problems encountered in production data pipelines.

### Duplicate Orders

An `order_id` can appear multiple times as the result of repeated ingestion. Each record contains an `updated_at` timestamp.

The pipeline resolves duplicates using a window function:

```sql
ROW_NUMBER() OVER (
    PARTITION BY order_id
    ORDER BY updated_at DESC
)
```

Only the newest version of each order is retained.

### Duplicate Customer Records

Customer records are also versioned. A `customer_id` may appear multiple times with different `record_version` values.

Customers are deduplicated before being joined to orders, retaining the highest version of each customer record. Performing this operation before the join prevents duplicate customer records from inflating order counts and revenue.

### Monetary Values Stored as Text

Price values can arrive in several forms, including:

```text
"$1,209.50"
"  42.99 "
""
```

The cleaning transformation normalizes these values and converts valid prices to numeric values before calculating line-level revenue.

Rows without usable quantity or price values are excluded from downstream calculations.

### Inconsistent Date Formats

`order_date` can contain multiple formats within the same dataset:

```text
05-Jan-2024
2024-01-05
01/05/2024
```

The SQL transformation attempts multiple parsing strategies using `TRY_STRPTIME` and combines them with `COALESCE`, allowing all supported formats to resolve into a consistent date representation without causing the entire query to fail when an individual parse attempt is unsuccessful.

### NULL Customer IDs

Some orders do not contain a `customer_id`.

Rather than allowing these records to disappear silently through an inner join, the pipeline handles them explicitly so that order totals reconcile:

```text
attributed orders + unassigned orders = all valid orders
```

This preserves visibility into revenue and orders that cannot be associated with a known customer.

## Repository Structure

| Path | Purpose |
| --- | --- |
| `docker-compose.yml` | Runs the local S3-compatible RustFS object store. |
| `scripts/generate_data.py` | Generates the intentionally messy source datasets. |
| `scripts/seed_s3.py` | Uploads generated source data into the S3 bucket. |
| `src/de_pipeline/config.py` | Contains S3 configuration and client setup. |
| `src/de_pipeline/fetch.py` | Downloads source objects from S3. |
| `src/de_pipeline/load.py` | Loads raw source data into DuckDB. |
| `src/de_pipeline/transform.py` | Coordinates transformation logic. |
| `src/de_pipeline/pipeline.py` | Runs the pipeline end to end. |
| `sql/` | Contains SQL transformation queries. |
| `tests/` | Automated tests covering ingestion and transformation behavior. |

## Transformation Pipeline

### 1. Source Ingestion

Source files are stored in a local S3-compatible object store provided by RustFS.

The pipeline fetches the source objects and loads them into raw DuckDB tables without modifying their contents. This preserves a raw representation of the upstream data before transformation.

### 2. Order Deduplication

The first transformation creates a deduplicated order dataset.

A CTE and `ROW_NUMBER()` window function partition records by `order_id` and rank them by `updated_at` in descending order.

The newest record for each order is retained.

### 3. Order Cleaning

The cleaned orders transformation standardizes fields and derives values required downstream.

It performs the following operations:

- Converts monetary text into numeric values.
- Normalizes order status using trimming and lowercase conversion.
- Converts blank status values to `unknown`.
- Parses multiple order-date formats.
- Calculates `line_total`.
- Removes rows without usable quantity or price information.

The resulting table provides a consistent representation of valid order records for downstream analysis.

### 4. Customer Deduplication and Order Summary

Customer records are deduplicated using their `record_version` before being joined with orders.

The customer summary produces one row per customer and aggregates order activity without allowing duplicate customer records to multiply joined rows.

The transformation also supports a configurable minimum-order threshold.

Rather than interpolating this value into SQL with an f-string, the implementation passes it as a bound SQL parameter:

```text
$min_orders
```

This keeps query structure separate from runtime values and avoids unnecessary dynamic SQL construction.

### 5. Tag Revenue Aggregation with Polars

Most transformations in the pipeline are implemented in SQL because they operate naturally on relational tables.

Tag-level revenue aggregation is implemented in **Polars**.

For this transformation, the tags associated with orders are exploded into individual rows and revenue is aggregated by tag. This operation maps cleanly to Polars' DataFrame API and demonstrates selecting a transformation tool based on the shape of the operation rather than using a single technology for every stage.

## SQL Organization

Transformation SQL is stored in dedicated `.sql` files under:

```text
sql/
```

Python is responsible for orchestration and parameter passing, while the transformation logic remains in SQL.

This separation keeps larger SQL statements easier to inspect, test, and maintain than embedding them directly inside Python source code.

## Setup

### Prerequisites

The project requires:

- Docker
- [`uv`](https://docs.astral.sh/uv/)
- Python dependencies defined by the project

### Initialize the Environment

Run the following commands in order:

```bash
uv sync
cp .env.example .env
docker compose up -d
uv run python scripts/generate_data.py
uv run python scripts/seed_s3.py
```

On Windows:

```text
copy .env.example .env
```

can be used instead of `cp`.

### Verify RustFS

After starting Docker, allow approximately 20–30 seconds for RustFS to become healthy.

Check its status with:

```bash
docker compose ps
```

The RustFS console is available locally on port `9001`, while the S3-compatible API runs on port `9000`.

## Running the Pipeline

Once RustFS is running and the source data has been generated and seeded, execute the complete pipeline with:

```bash
uv run de-pipeline
```

The pipeline performs the full workflow from source ingestion through transformation and aggregation.

## Testing

The project includes automated tests for ingestion, transformation behavior, data-quality handling, and end-to-end orchestration.

Run the complete test suite with:

```bash
uv run pytest
```

Run only the transformation tests:

```bash
uv run pytest tests/test_transform.py
```

Run an individual test:

```bash
uv run pytest tests/test_transform.py::test_name
```

The transformation tests cover behavior including:

- Keeping the newest duplicate order.
- Cleaning and casting monetary values.
- Removing unusable records.
- Producing one customer-summary row per customer.
- Using a bound parameter for minimum-order filtering.
- Exploding tags and aggregating revenue with Polars.
- Parsing all supported order-date formats.
- Handling orders with NULL customer IDs.
- Running the complete transformation workflow.

Some S3-dependent tests require RustFS to be running and seeded.

## Linting

Run Ruff across the project with:

```bash
uv run ruff check .
```

Ruff can also be integrated with VS Code to surface lint issues directly in the editor.

## Design Decisions

### SQL for Relational Transformations

SQL is the primary transformation language in this project because most operations are naturally set-based:

- filtering
- joining
- aggregation
- deduplication
- window functions
- type conversion

Running these transformations directly in DuckDB also avoids moving data unnecessarily between processing environments.

### Polars for DataFrame-Oriented Work

Polars is used selectively rather than as a replacement for SQL.

The tag-revenue transformation requires exploding a collection into individual rows and aggregating over those values. This operation is concise and readable using Polars' DataFrame API.

The resulting architecture demonstrates a broader engineering principle: choose the processing tool that expresses each transformation clearly rather than forcing every operation into the same abstraction.

### Defensive Parsing

Potentially malformed source values are handled using operations such as:

```sql
TRY_CAST(...)
TRY_STRPTIME(...)
```

This prevents a single malformed value from terminating an entire transformation.

Invalid values can instead become `NULL` and then be handled explicitly according to the pipeline's data-quality rules.

### Explicit NULL Handling

NULL join keys are treated as a data-quality condition rather than being allowed to disappear implicitly during joins.

Keeping unassigned orders visible ensures downstream totals remain reconcilable and makes missing customer attribution observable.

### Parameterized SQL

Runtime values are passed to SQL through bound parameters rather than string interpolation.

This produces clearer separation between SQL logic and application values and avoids constructing dynamic queries unnecessarily.

## Troubleshooting

### RustFS remains `starting` or `unhealthy`

Allow 20–30 seconds after starting the containers, then check:

```bash
docker compose ps
```

If the service remains unhealthy:

```bash
docker compose logs rustfs
```

### Ports 9000 or 9001 are already in use

Another RustFS instance may already be running.

Stop the conflicting container or change the host-side ports in `docker-compose.yml` and update `S3_ENDPOINT_URL` in `.env` accordingly.

### `seed_s3.py` cannot connect

Confirm that RustFS is running and healthy before attempting to seed the source bucket.

### Money or date conversion fails

The transformations use tolerant parsing operations such as `TRY_CAST` and `TRY_STRPTIME` where malformed source values are possible.

These operations convert unsuccessful parses to `NULL`, allowing invalid values to be handled deliberately instead of terminating the entire query.

### VS Code does not detect the environment

Open the Command Palette and select:

```text
Python: Select Interpreter
```

Then choose the Python interpreter under `.venv`.

## Key Engineering Concepts Demonstrated

This project demonstrates several patterns relevant to production data engineering:

- Object-store-based source ingestion
- Raw-to-transformed data flow
- DuckDB-based analytical processing
- SQL window functions for deterministic deduplication
- Version-aware dimension deduplication
- Defensive type conversion
- Multi-format date normalization
- Explicit NULL handling and reconciliation
- Parameterized SQL
- SQL/Python separation
- Polars DataFrame transformations
- Automated pipeline testing
- End-to-end pipeline orchestration
- Tool selection based on transformation characteristics

The result is a reproducible pipeline that takes intentionally inconsistent upstream data and produces cleaned, deduplicated, and aggregated datasets while preserving visibility into data-quality issues.
