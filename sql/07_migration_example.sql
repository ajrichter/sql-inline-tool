-- ============================================================
-- 07_migration_example.sql
-- Full old→new migration validation using example data
-- ============================================================
-- This demonstrates validating a real schema migration:
--   - dept_code → department_id (FK lookup)
--   - is_active INTEGER → BOOLEAN
--   - date strings → TIMESTAMP
--   - orders gained a computed total_amount column
--
-- Run:
--   duckdb < sql/07_migration_example.sql
-- ============================================================

-- ===== LOAD OLD AND NEW DATA =====

CREATE TABLE old_users AS SELECT * FROM read_csv_auto('examples/old_users.csv');
CREATE TABLE new_users AS SELECT * FROM read_csv_auto('examples/new_users.csv');
CREATE TABLE old_depts AS SELECT * FROM read_csv_auto('examples/old_departments.csv');
CREATE TABLE new_depts AS SELECT * FROM read_csv_auto('examples/new_departments.csv');
CREATE TABLE old_orders AS SELECT * FROM read_csv_auto('examples/old_orders.csv');
CREATE TABLE new_orders AS SELECT * FROM read_csv_auto('examples/new_orders.csv');

-- ===== VALIDATION RESULTS TABLE =====
CREATE TABLE results (check_name VARCHAR, status VARCHAR, detail VARCHAR);


-- ----- USERS TABLE VALIDATIONS -----

-- Row count
INSERT INTO results
SELECT 'users_row_count',
    CASE WHEN o.cnt = n.cnt THEN 'PASS' ELSE 'FAIL' END,
    'old=' || o.cnt || ' new=' || n.cnt
FROM (SELECT COUNT(*) cnt FROM old_users) o,
     (SELECT COUNT(*) cnt FROM new_users) n;

-- All old user_ids exist in new
INSERT INTO results
SELECT 'users_no_data_loss',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' users lost'
FROM old_users o LEFT JOIN new_users n ON o.user_id = n.user_id
WHERE n.user_id IS NULL;

-- dept_code → department_id mapping is correct
INSERT INTO results
SELECT 'users_dept_mapping',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' mismatched department mappings'
FROM old_users o
JOIN new_depts d ON o.dept_code = d.department_code
JOIN new_users n ON o.user_id = n.user_id
WHERE n.department_id != d.id;

-- is_active conversion (1→true, 0→false)
INSERT INTO results
SELECT 'users_is_active_conversion',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' incorrect is_active conversions'
FROM old_users o
JOIN new_users n ON o.user_id = n.user_id
WHERE (o.is_active = 1 AND n.is_active != true)
   OR (o.is_active = 0 AND n.is_active != false);

-- Name and salary unchanged
INSERT INTO results
SELECT 'users_values_preserved',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' rows with changed name/salary'
FROM old_users o
JOIN new_users n ON o.user_id = n.user_id
WHERE o.first_name != n.first_name
   OR o.last_name != n.last_name
   OR o.salary != n.salary;


-- ----- DEPARTMENTS TABLE VALIDATIONS -----

-- Row count
INSERT INTO results
SELECT 'depts_row_count',
    CASE WHEN o.cnt = n.cnt THEN 'PASS' ELSE 'FAIL' END,
    'old=' || o.cnt || ' new=' || n.cnt
FROM (SELECT COUNT(*) cnt FROM old_depts) o,
     (SELECT COUNT(*) cnt FROM new_depts) n;

-- All old dept_codes exist as department_code in new
INSERT INTO results
SELECT 'depts_code_preserved',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' department codes lost'
FROM old_depts o
LEFT JOIN new_depts n ON o.dept_code = n.department_code
WHERE n.department_code IS NULL;

-- dept_name and budget preserved
INSERT INTO results
SELECT 'depts_values_preserved',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' depts with changed name/budget'
FROM old_depts o
JOIN new_depts n ON o.dept_code = n.department_code
WHERE o.dept_name != n.dept_name
   OR o.budget IS DISTINCT FROM n.budget;


-- ----- ORDERS TABLE VALIDATIONS -----

-- Row count
INSERT INTO results
SELECT 'orders_row_count',
    CASE WHEN o.cnt = n.cnt THEN 'PASS' ELSE 'FAIL' END,
    'old=' || o.cnt || ' new=' || n.cnt
FROM (SELECT COUNT(*) cnt FROM old_orders) o,
     (SELECT COUNT(*) cnt FROM new_orders) n;

-- total_amount computed correctly (quantity * unit_price)
INSERT INTO results
SELECT 'orders_total_amount',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' orders with incorrect total_amount'
FROM new_orders
WHERE ABS(total_amount - (quantity * unit_price)) > 0.01;

-- status → status_code mapping preserved
INSERT INTO results
SELECT 'orders_status_preserved',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' orders with changed status'
FROM old_orders o
JOIN new_orders n ON o.order_id = n.order_id
WHERE o.status != n.status_code;

-- Core values unchanged
INSERT INTO results
SELECT 'orders_values_preserved',
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    COUNT(*) || ' orders with changed core values'
FROM old_orders o
JOIN new_orders n ON o.order_id = n.order_id
WHERE o.user_id != n.user_id
   OR o.product_code != n.product_code
   OR o.quantity != n.quantity
   OR o.unit_price != n.unit_price;


-- ===== FINAL REPORT =====
SELECT * FROM results ORDER BY check_name;

SELECT
    '===== SUMMARY =====' as label,
    COUNT(*) as total_checks,
    SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as passed,
    SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) as failed
FROM results;
