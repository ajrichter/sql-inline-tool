-- ============================================================
-- 04_query_examples.sql
-- Flexible query patterns for Claude Code to use with DuckDB
-- ============================================================
-- These patterns show how to query CSV and Parquet files directly
-- without needing to load them into a database first.
-- ============================================================

-- ----- DIRECT FILE QUERIES (no CREATE TABLE needed) -----

-- Query a CSV file directly
SELECT * FROM read_csv_auto('examples/source_data.csv') LIMIT 5;

-- Query a Parquet file directly
-- SELECT * FROM read_parquet('checkpoints/source_data.parquet') LIMIT 5;

-- Query with filtering
SELECT name, salary
FROM read_csv_auto('examples/source_data.csv')
WHERE status = 'active'
ORDER BY salary DESC;

-- ----- AGGREGATION -----

SELECT
    department_code,
    COUNT(*) as headcount,
    AVG(salary) as avg_salary,
    SUM(salary) as total_salary
FROM read_csv_auto('examples/source_data.csv')
GROUP BY department_code
ORDER BY total_salary DESC;

-- ----- JOIN FILES DIRECTLY -----

-- Join source data with department mapping
SELECT
    s.name,
    s.department_code as old_dept,
    m.new_code as new_dept,
    s.salary
FROM read_csv_auto('examples/source_data.csv') s
JOIN read_csv_auto('examples/department_mapping.csv') m
    ON s.department_code = m.old_code;

-- ----- COMPARE TWO DATASETS -----

-- Find all differences between source and target
SELECT
    COALESCE(s.id, t.id) as id,
    s.department_code as old_dept,
    t.department_code as new_dept,
    CASE
        WHEN s.id IS NULL THEN 'ADDED'
        WHEN t.id IS NULL THEN 'REMOVED'
        WHEN s.department_code != t.department_code THEN 'CHANGED'
        ELSE 'SAME'
    END as change_type
FROM read_csv_auto('examples/source_data.csv') s
FULL OUTER JOIN read_csv_auto('examples/target_data.csv') t ON s.id = t.id
WHERE s.department_code IS DISTINCT FROM t.department_code
   OR s.id IS NULL
   OR t.id IS NULL;

-- ----- GLOB PATTERNS (query multiple files at once) -----

-- Query all CSV files matching a pattern
SELECT * FROM read_csv_auto('examples/*_data.csv', union_by_name=true) LIMIT 10;
