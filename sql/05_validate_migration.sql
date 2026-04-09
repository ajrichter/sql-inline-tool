-- ============================================================
-- 05_validate_migration.sql
-- Inline validation checks comparing pre- and post-migration data
-- ============================================================
-- Usage:
--   duckdb < sql/05_validate_migration.sql
--
-- Each validation returns rows only when there is a PROBLEM.
-- Empty result = PASS. Any rows returned = FAIL.
-- ============================================================

-- ----- VALIDATION 1: Row count comparison -----
SELECT
    'row_count_check' as check_name,
    src.cnt as source_rows,
    tgt.cnt as target_rows,
    CASE WHEN src.cnt = tgt.cnt THEN 'PASS' ELSE 'FAIL' END as status
FROM
    (SELECT COUNT(*) as cnt FROM read_csv_auto('examples/source_data.csv')) src,
    (SELECT COUNT(*) as cnt FROM read_csv_auto('examples/target_data.csv')) tgt;


-- ----- VALIDATION 2: No NULL IDs in target -----
SELECT 'null_id_check' as check_name, *
FROM read_csv_auto('examples/target_data.csv')
WHERE id IS NULL;


-- ----- VALIDATION 3: No duplicate IDs in target -----
SELECT 'duplicate_id_check' as check_name, id, COUNT(*) as cnt
FROM read_csv_auto('examples/target_data.csv')
GROUP BY id
HAVING COUNT(*) > 1;


-- ----- VALIDATION 4: All department codes are mapped -----
SELECT 'unmapped_dept_check' as check_name, t.department_code, COUNT(*) as cnt
FROM read_csv_auto('examples/target_data.csv') t
LEFT JOIN read_csv_auto('examples/department_mapping.csv') m
    ON t.department_code = m.new_code
WHERE m.new_code IS NULL
GROUP BY t.department_code;


-- ----- VALIDATION 5: Value diff between source and target -----
-- Shows rows where non-key values differ (excluding expected mapping changes)
SELECT
    'value_diff' as check_name,
    COALESCE(s.id, t.id) as id,
    s.name as src_name,
    t.name as tgt_name,
    s.salary as src_salary,
    t.salary as tgt_salary,
    s.status as src_status,
    t.status as tgt_status
FROM read_csv_auto('examples/source_data.csv') s
FULL OUTER JOIN read_csv_auto('examples/target_data.csv') t ON s.id = t.id
WHERE s.name IS DISTINCT FROM t.name
   OR s.salary IS DISTINCT FROM t.salary
   OR s.status IS DISTINCT FROM t.status
   OR s.id IS NULL
   OR t.id IS NULL;


-- ----- VALIDATION 6: Department mapping was applied correctly -----
SELECT
    'mapping_applied_check' as check_name,
    s.id,
    s.department_code as old_dept,
    m.new_code as expected_dept,
    t.department_code as actual_dept
FROM read_csv_auto('examples/source_data.csv') s
JOIN read_csv_auto('examples/department_mapping.csv') m
    ON s.department_code = m.old_code
JOIN read_csv_auto('examples/target_data.csv') t
    ON s.id = t.id
WHERE t.department_code != m.new_code;
