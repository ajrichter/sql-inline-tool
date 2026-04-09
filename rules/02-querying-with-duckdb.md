# Rule 2: How to Query Using DuckDB

## Registering Files

Before querying, register your data files with the query engine:

```python
from sql_inline_tool.query import QueryEngine

engine = QueryEngine()

# Register individual files
engine.register_csv("data/users.csv")           # → table "users"
engine.register_csv("data/orders.csv", "orders") # → table "orders"
engine.register_parquet("checkpoints/users.parquet")

# Register a whole directory
engine.register_directory("data/", pattern="*.csv")

# See what's available
print(engine.tables())
print(engine.describe("users"))
```

## Running Queries

```python
# As list of dicts
rows = engine.query("SELECT * FROM users WHERE age > 30")

# As pandas DataFrame
df = engine.query_df("SELECT department, COUNT(*) FROM users GROUP BY 1")

# As JSON string
json_str = engine.to_json("SELECT * FROM users LIMIT 10", pretty=True)

# Query a file directly without registering
rows = engine.query_file("SELECT COUNT(*) FROM data", "data/users.csv")
```

## CLI Queries

```bash
# Query CSV files directly
sql-inline query "SELECT * FROM users LIMIT 5" --csv data/users.csv

# Query with JSON output
sql-inline query "SELECT COUNT(*) as total FROM users" --csv data/users.csv -j

# Query Parquet checkpoints
sql-inline query "SELECT * FROM users" --parquet checkpoints/users.parquet
```

## Useful DuckDB SQL Patterns

### Joining files directly (no registration needed)

```sql
SELECT a.*, b.category
FROM read_csv_auto('data/orders.csv') a
JOIN read_csv_auto('data/categories.csv') b ON a.cat_id = b.id
```

### Aggregation and window functions

```sql
SELECT
    department,
    COUNT(*) as headcount,
    AVG(salary) as avg_salary,
    SUM(salary) as total_salary
FROM read_csv_auto('data/employees.csv')
GROUP BY department
ORDER BY total_salary DESC
```

### Comparing two versions of a dataset

```sql
SELECT
    COALESCE(a.id, b.id) as id,
    a.value as old_value,
    b.value as new_value,
    CASE
        WHEN a.id IS NULL THEN 'ADDED'
        WHEN b.id IS NULL THEN 'REMOVED'
        WHEN a.value != b.value THEN 'CHANGED'
    END as change_type
FROM read_csv_auto('data/before.csv') a
FULL OUTER JOIN read_csv_auto('data/after.csv') b ON a.id = b.id
WHERE a.value IS DISTINCT FROM b.value
   OR a.id IS NULL
   OR b.id IS NULL
```
