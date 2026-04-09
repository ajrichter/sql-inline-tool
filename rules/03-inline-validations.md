# Rule 3: Repeatable Queries and Inline Validations

## What Are Inline Validations?

Inline validations are SQL-based checks that run against your data **before
and after** a migration to confirm correctness. They answer questions like:

- Did we lose any rows?
- Do all values map correctly to the new schema?
- Are there unexpected NULLs or duplicates?
- Does the migrated data match expected transformations?

## Using the Validator

### Python API

```python
from sql_inline_tool.query import QueryEngine
from sql_inline_tool.validator import InlineValidator

engine = QueryEngine()
engine.register_csv("data/source.csv", "source")
engine.register_csv("data/target.csv", "target")
engine.register_csv("data/mappings.csv", "mappings")

validator = InlineValidator(engine)

# Check row counts match
validator.check_row_count("source", "target")

# Check schema compatibility
validator.check_schema_compatibility("source", "target")

# Check value mappings
validator.check_mapping("target", "mappings", "old_code", "new_code")

# Diff the tables on key columns
validator.diff_tables("source", "target", key_columns=["id"])

# Custom SQL assertion — passes if query returns 0 rows (no violations)
validator.check_sql(
    "SELECT * FROM target WHERE status IS NULL",
    name="no_null_status"
)

# Print report
print(validator.report.summary())
print(validator.report.to_json())
```

### CLI

```bash
sql-inline validate \
    --source data/source.csv \
    --target data/target.csv \
    --key id \
    --mapping data/mappings.csv \
    --mapping-source-col old_code \
    --mapping-target-col new_code \
    --json-output
```

## Writing Validation Rules as CSV

Create a CSV file with your validation rules:

```csv
name,type,sql,expect_empty
no_null_ids,sql_assertion,"SELECT * FROM target WHERE id IS NULL",true
no_duplicates,sql_assertion,"SELECT id, COUNT(*) FROM target GROUP BY id HAVING COUNT(*) > 1",true
all_mapped,sql_assertion,"SELECT * FROM target t LEFT JOIN mappings m ON t.code = m.new_code WHERE m.new_code IS NULL",true
has_data,sql_assertion,"SELECT 1 FROM target LIMIT 1",false
```

Run the suite:

```python
validator.run_validation_suite("rules/validation_rules.csv")
```

Or via CLI:

```bash
sql-inline validate -s source.csv -t target.csv -k id --rules rules/validation_rules.csv
```

## Comparing Two Outputs (Pre vs Post Migration)

The `diff_tables` method performs a FULL OUTER JOIN on key columns and reports:

- **Added rows**: exist in target but not source
- **Removed rows**: exist in source but not target
- **Changed rows**: key matches but values differ

```python
validator.diff_tables(
    source_table="pre_migration",
    target_table="post_migration",
    key_columns=["user_id", "account_id"],
    compare_columns=["balance", "status", "updated_at"],
)
```

## Checkpointing for Repeatable Comparisons

Save your current state as Parquet so you can re-run validations later:

```python
from sql_inline_tool.ingest import ingest_csv, checkpoint_all

conn = ingest_csv("data/current_state.csv")
checkpoint_all(conn, "checkpoints/2024-01-15/")
```

Then compare against a future state:

```python
engine = QueryEngine()
engine.register_parquet("checkpoints/2024-01-15/current_state.parquet", "baseline")
engine.register_csv("data/new_state.csv", "current")

validator = InlineValidator(engine)
validator.diff_tables("baseline", "current", key_columns=["id"])
```

## Schema Migration Validation

Convert your SQL schemas to CSV rules for tracking:

```bash
# Extract rules from a SQL file
sql-inline schema2csv migrations/001_create_tables.sql -o rules/schema_v1.csv

# Compare schemas by loading both rule files
sql-inline query \
    "SELECT a.*, b.data_type as new_type
     FROM v1 a LEFT JOIN v2 b ON a.table = b.table AND a.column = b.column
     WHERE a.data_type != b.data_type OR b.column IS NULL" \
    --csv rules/schema_v1.csv:v1 \
    --csv rules/schema_v2.csv:v2
```
