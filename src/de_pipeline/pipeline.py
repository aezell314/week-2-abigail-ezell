"""Day 3 — wire the stages into one end-to-end run.

This is the entry point for ``uv run de-pipeline``. By the end of the week it
should run the whole pipeline — fetch from S3 -> load into DuckDB -> run the
transforms — printing a short summary so a human can see what happened.
"""

from __future__ import annotations

from de_pipeline import fetch, load, transform  # noqa: F401


def main() -> None:
    """Run the full pipeline end to end: fetch the source files, open a DuckDB
    connection, load the raw tables, run the transforms, and print a summary."""
    print("Fetching raw files...")
    paths = fetch.fetch_all()

    for name, path in paths.items():
        print(f"Successfully downloaded {name} to {path}")

    print("Loading raw files into a DuckDB warehouse...")
    con = load.connect()
    loads = load.load_all(con)
    for name, rows in loads.items():
        print(f"Successfully loaded table \'{name}\' with {rows} rows")

    print("Cleaning and aggregating raw data using DuckDB and Polars...")
    transforms = transform.run_transforms(con)
    for name, rows in transforms.items():
        print(f"Successfully loaded table \'{name}\' with {rows} rows")


if __name__ == "__main__":
    main()
