-- ============================================================
-- 01_ingest_csv.sql
-- Ingest CSV files into DuckDB tables
-- ============================================================
-- Usage: Run with DuckDB CLI or from any DuckDB connection.
--   duckdb < sql/01_ingest_csv.sql
--   duckdb mydb.duckdb < sql/01_ingest_csv.sql
--
-- Override file paths with DuckDB variables:
--   duckdb -cmd "SET VARIABLE source_csv='path/to/file.csv'" < sql/01_ingest_csv.sql
-- ============================================================

-- Load a single CSV into a table
CREATE OR REPLACE TABLE source_data AS
SELECT * FROM read_csv_auto('examples/source_data.csv');

CREATE OR REPLACE TABLE target_data AS
SELECT * FROM read_csv_auto('examples/target_data.csv');

CREATE OR REPLACE TABLE department_mapping AS
SELECT * FROM read_csv_auto('examples/department_mapping.csv');

-- Verify loaded data
SELECT 'source_data' as table_name, COUNT(*) as row_count FROM source_data
UNION ALL
SELECT 'target_data', COUNT(*) FROM target_data
UNION ALL
SELECT 'department_mapping', COUNT(*) FROM department_mapping;
