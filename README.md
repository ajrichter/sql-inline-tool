# sql-inline-tool

Inline validation of SQL scripts pre- and post-migration using [DuckDB](https://duckdb.org/).

Inspired by: https://simonwillison.net/2022/Sep/1/sqlite-duckdb-paper/

## What This Does

Validates SQL migration correctness by querying CSV/Parquet data files directly with DuckDB. No database server needed — DuckDB runs in-process and reads files where they sit.

**Core capabilities:**
- Ingest CSV files and query them with SQL (no ETL needed)
- Checkpoint CSV data as Parquet files for repeatable comparisons
- Extract schema rules from SQL DDL into CSV
- Run inline validations comparing old vs new data
- All logic lives in DuckDB SQL — Python is only used for a test harness

## Setup

```bash
pip install duckdb pyarrow
```

That's it. No server, no config.

## Project Layout

```
sql/                          # DuckDB SQL scripts (the core of the tool)
├── 01_ingest_csv.sql         # Load CSVs into DuckDB tables
├── 02_checkpoint_parquet.sql # Save tables as Parquet checkpoints
├── 03_schema_to_csv.sql      # Extract schema metadata to CSV
├── 04_query_examples.sql     # Query patterns for Claude Code
├── 05_validate_migration.sql # Validation checks (simple example)
├── 06_repeatable_validation.sql  # Template for repeatable validation suites
└── 07_migration_example.sql  # Full old→new migration validation

examples/                     # Sample data files
├── old_schema.sql            # Pre-migration DDL
├── new_schema.sql            # Post-migration DDL
├── old_users.csv             # Pre-migration users
├── new_users.csv             # Post-migration users
├── old_departments.csv       # Pre-migration departments
├── new_departments.csv       # Post-migration departments
├── old_orders.csv            # Pre-migration orders
├── new_orders.csv            # Post-migration orders
├── department_mapping.csv    # Code mapping table
├── source_data.csv           # Simple source data
├── target_data.csv           # Simple target data
└── validation_rules.csv      # CSV-defined validation rules

rules/                        # Documentation
├── 01-setup-dependencies.md
├── 02-querying-with-duckdb.md
└── 03-inline-validations.md

test_duckdb.py                # Mini Python test suite
sql_inline_tool/              # Python library (optional CLI wrapper)
```

## How to Run

### Query CSV files directly with DuckDB SQL

No loading step needed — just query the files:

```sql
-- In any DuckDB connection (CLI, Python, etc.)
SELECT * FROM read_csv_auto('examples/old_users.csv') LIMIT 5;

-- Join two CSVs
SELECT u.first_name, d.dept_name
FROM read_csv_auto('examples/old_users.csv') u
JOIN read_csv_auto('examples/old_departments.csv') d
    ON u.dept_code = d.dept_code;

-- Aggregate
SELECT dept_code, COUNT(*) as headcount, AVG(salary) as avg_salary
FROM read_csv_auto('examples/old_users.csv')
GROUP BY dept_code;
```

### Run the migration validation example

This validates a full old→new schema migration (users, departments, orders):

```bash
# From Python
python -c "
import duckdb
conn = duckdb.connect(':memory:')
conn.execute(open('sql/07_migration_example.sql').read())
for row in conn.execute('SELECT * FROM results ORDER BY check_name').fetchall():
    print(f'  [{row[1]}] {row[0]}: {row[2]}')
"
```

Output:
```
  [PASS] depts_code_preserved: 0 department codes lost
  [PASS] depts_row_count: old=5 new=5
  [PASS] depts_values_preserved: 0 depts with changed name/budget
  [PASS] orders_row_count: old=6 new=6
  [PASS] orders_status_preserved: 0 orders with changed status
  [PASS] orders_total_amount: 0 orders with incorrect total_amount
  [PASS] orders_values_preserved: 0 orders with changed core values
  [PASS] users_dept_mapping: 0 mismatched department mappings
  [PASS] users_is_active_conversion: 0 incorrect is_active conversions
  [PASS] users_no_data_loss: 0 users lost
  [PASS] users_row_count: old=7 new=7
  [PASS] users_values_preserved: 0 rows with changed name/salary
```

### Run the test suite

```bash
python test_duckdb.py
```

Runs 16 DuckDB-based tests covering ingestion, parquet roundtrip, schema extraction, direct file queries, and inline validations.

### Run individual SQL scripts

```bash
# From Python (each script is self-contained)
python -c "import duckdb; duckdb.connect(':memory:').execute(open('sql/05_validate_migration.sql').read())"
```

### Checkpoint data as Parquet

```sql
-- Save current state
COPY (SELECT * FROM read_csv_auto('examples/old_users.csv'))
TO 'checkpoints/users_baseline.parquet' (FORMAT PARQUET);

-- Later, compare against new data
SELECT o.user_id, o.salary as old_salary, n.salary as new_salary
FROM read_parquet('checkpoints/users_baseline.parquet') o
JOIN read_csv_auto('examples/new_users.csv') n ON o.user_id = n.user_id
WHERE o.salary != n.salary;
```

## Writing Your Own Validations

Each validation is a SQL query that returns rows **only when there's a problem**. Empty result = PASS.

```sql
-- Create a results collector
CREATE TABLE results (check_name VARCHAR, status VARCHAR, detail VARCHAR);

-- Add your checks
INSERT INTO results
SELECT 'my_check',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' violations found'
FROM read_csv_auto('my_target.csv')
WHERE some_column IS NULL;

-- Review
SELECT * FROM results;
```

### Old→New Migration Pattern

When your schema changes column names, types, or structure:

```sql
-- Validate dept_code → department_id FK mapping
INSERT INTO results
SELECT 'dept_fk_mapping',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' bad FK mappings'
FROM read_csv_auto('old_data.csv') o
JOIN read_csv_auto('dept_mapping.csv') m ON o.dept_code = m.old_code
JOIN read_csv_auto('new_data.csv') n ON o.id = n.id
WHERE n.department_id != m.new_id;

-- Validate type conversion (INTEGER → BOOLEAN)
INSERT INTO results
SELECT 'bool_conversion',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' bad bool conversions'
FROM read_csv_auto('old_data.csv') o
JOIN read_csv_auto('new_data.csv') n ON o.id = n.id
WHERE (o.is_active = 1 AND n.is_active != true)
   OR (o.is_active = 0 AND n.is_active != false);

-- Validate computed columns
INSERT INTO results
SELECT 'total_amount_check',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' bad totals'
FROM read_csv_auto('new_orders.csv')
WHERE ABS(total_amount - (quantity * unit_price)) > 0.01;
```

## Using with Claude Code

Drop your CSV/Parquet files in the project, then ask Claude Code to:
- Query files: `"Query examples/old_users.csv to show salary by department"`
- Validate: `"Run sql/07_migration_example.sql and show me the results"`
- Compare: `"Diff old_users.csv against new_users.csv on user_id"`
- Add checks: `"Add a validation to 07_migration_example.sql checking email format"`

The SQL scripts in `sql/` and patterns in `rules/` give Claude Code the context to write correct DuckDB queries.
