-- ============================================================
-- 03_schema_to_csv.sql
-- Extract schema information from tables and export as CSV rules
-- ============================================================
-- Usage:
--   duckdb mydb.duckdb < sql/03_schema_to_csv.sql
--
-- This creates a schema_rules table and exports it as a CSV file
-- that documents the structure of your tables.
-- ============================================================

-- Extract column metadata from all tables in the main schema
CREATE OR REPLACE TABLE schema_rules AS
SELECT
    table_name as "table",
    column_name as "column",
    data_type,
    CASE WHEN is_nullable = 'YES' THEN true ELSE false END as nullable,
    column_default as "default"
FROM information_schema.columns
WHERE table_schema = 'main'
  AND table_name NOT IN ('schema_rules')
ORDER BY table_name, ordinal_position;

-- Show the extracted rules
SELECT * FROM schema_rules;

-- Export as CSV
COPY schema_rules TO 'rules/schema_rules.csv' (HEADER, DELIMITER ',');
