"""de_pipeline — your Week 2 data engineering pipeline.

Week 1 got the data from S3 into DuckDB and ran a couple of basic transforms.
Week 2's theme is *"your transforms are basic — let's get serious."* The source
data is messier now (duplicate records, NULL join keys, money stored as text,
dates in three different formats), and the job is real, DE-flavored SQL:

    fetch.py      Day 1 (warm-up) — pull the raw CSV + JSON down from S3 (RustFS)
    load.py       Day 1 (warm-up) — load both files into DuckDB
    transform.py  Day 1-3        — dedup, clean, and combine with serious SQL
    pipeline.py   Day 3          — wire fetch -> load -> transform into one run

config.py is provided for you (S3 settings + client). The fetch/load layer is a
quick re-run of Week 1's muscle memory; the real work this week lives in
transform.py, the sql/ files, and one transform you'll deliberately do in Polars.
"""

__all__ = ["__version__"]
__version__ = "0.2.0"
