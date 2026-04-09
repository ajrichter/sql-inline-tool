-- ============================================================
-- 06_repeatable_validation.sql
-- Template for repeatable inline validations
-- ============================================================
-- This is a parameterized template. Replace the file paths
-- with your actual source/target files.
--
-- Pattern: Each check returns a single summary row with
-- check_name, status (PASS/FAIL), and detail.
-- ============================================================

-- Create a results table to collect all check outcomes
CREATE OR REPLACE TABLE validation_results (
    check_name VARCHAR,
    status VARCHAR,
    detail VARCHAR
);

-- Check 1: Row counts match
INSERT INTO validation_results
SELECT
    'row_count' as check_name,
    CASE WHEN src.cnt = tgt.cnt THEN 'PASS' ELSE 'FAIL' END as status,
    'source=' || src.cnt || ' target=' || tgt.cnt as detail
FROM
    (SELECT COUNT(*) as cnt FROM read_csv_auto('examples/source_data.csv')) src,
    (SELECT COUNT(*) as cnt FROM read_csv_auto('examples/target_data.csv')) tgt;

-- Check 2: No NULL keys
INSERT INTO validation_results
SELECT
    'no_null_keys' as check_name,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END as status,
    COUNT(*) || ' rows with NULL id' as detail
FROM read_csv_auto('examples/target_data.csv')
WHERE id IS NULL;

-- Check 3: No duplicates on key
INSERT INTO validation_results
SELECT
    'no_duplicate_keys' as check_name,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END as status,
    COUNT(*) || ' duplicate ids found' as detail
FROM (
    SELECT id FROM read_csv_auto('examples/target_data.csv')
    GROUP BY id HAVING COUNT(*) > 1
);

-- Check 4: All values mapped
INSERT INTO validation_results
SELECT
    'all_values_mapped' as check_name,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END as status,
    COUNT(*) || ' unmapped department codes' as detail
FROM (
    SELECT DISTINCT t.department_code
    FROM read_csv_auto('examples/target_data.csv') t
    LEFT JOIN read_csv_auto('examples/department_mapping.csv') m
        ON t.department_code = m.new_code
    WHERE m.new_code IS NULL
);

-- Check 5: No data loss (all source IDs exist in target)
INSERT INTO validation_results
SELECT
    'no_data_loss' as check_name,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END as status,
    COUNT(*) || ' source rows missing from target' as detail
FROM read_csv_auto('examples/source_data.csv') s
LEFT JOIN read_csv_auto('examples/target_data.csv') t ON s.id = t.id
WHERE t.id IS NULL;

-- ===== FINAL REPORT =====
SELECT * FROM validation_results;

-- Summary
SELECT
    COUNT(*) as total_checks,
    SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as passed,
    SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) as failed
FROM validation_results;
