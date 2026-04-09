# Rule 1: Setting Up Dependencies

## Install

```bash
pip install -e ".[dev]"
```

For Snowflake connectivity (optional):

```bash
pip install -e ".[snowflake]"
```

## Core Dependencies

| Package  | Purpose |
|----------|---------|
| `duckdb` | In-process SQL engine for querying CSV/Parquet files directly |
| `pyarrow` | Parquet read/write and Arrow columnar format support |
| `pandas` | DataFrame output for query results |
| `click` | CLI framework |

## How DuckDB Works Here

DuckDB runs **in-process** — no server needed. It reads CSV and Parquet files
directly via SQL, which means:

- No ETL pipeline to set up
- No database to provision
- Files are queried where they sit on disk
- Results stay in memory or get checkpointed to Parquet

## Project Layout

```
sql_inline_tool/
├── ingest.py           # CSV → DuckDB → Parquet ingestion
├── schema_converter.py # SQL DDL ↔ CSV rules conversion
├── query.py            # Flexible query engine
├── validator.py        # Pre/post migration validation
└── cli.py              # Command-line interface
```

## Quick Start

```python
from sql_inline_tool.query import QueryEngine

engine = QueryEngine()
engine.register_csv("data/mappings.csv")
results = engine.query("SELECT * FROM mappings WHERE status = 'active'")
```
