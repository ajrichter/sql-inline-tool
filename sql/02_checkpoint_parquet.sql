-- ============================================================
-- 02_checkpoint_parquet.sql
-- Save DuckDB tables as Parquet checkpoint files
-- ============================================================
-- Usage:
--   duckdb mydb.duckdb < sql/02_checkpoint_parquet.sql
-- ============================================================

-- Export tables to Parquet checkpoint files
COPY source_data TO 'checkpoints/source_data.parquet' (FORMAT PARQUET);
COPY target_data TO 'checkpoints/target_data.parquet' (FORMAT PARQUET);
COPY department_mapping TO 'checkpoints/department_mapping.parquet' (FORMAT PARQUET);

-- Verify by reading back from Parquet
SELECT 'source_data.parquet' as file, COUNT(*) as rows
FROM read_parquet('checkpoints/source_data.parquet')
UNION ALL
SELECT 'target_data.parquet', COUNT(*)
FROM read_parquet('checkpoints/target_data.parquet')
UNION ALL
SELECT 'department_mapping.parquet', COUNT(*)
FROM read_parquet('checkpoints/department_mapping.parquet');
