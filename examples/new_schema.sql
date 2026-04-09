-- ============================================================
-- NEW SCHEMA (post-migration)
-- ============================================================
-- Changes from old schema:
--   - users.is_active INTEGER → users.is_active BOOLEAN
--   - users.created_date VARCHAR → users.created_at TIMESTAMP
--   - users.dept_code → users.department_id (FK to departments.id)
--   - departments.dept_code → departments.id (INTEGER, auto-inc)
--   - departments added: department_code VARCHAR (holds old dept_code)
--   - orders.order_date VARCHAR → orders.ordered_at TIMESTAMP
--   - orders.status VARCHAR → orders.status_code VARCHAR(20)
--   - orders added: total_amount DECIMAL (quantity * unit_price)
-- ============================================================

CREATE TABLE departments (
    id INTEGER NOT NULL PRIMARY KEY,
    department_code VARCHAR(10) NOT NULL,
    dept_name VARCHAR(100) NOT NULL,
    manager_id INTEGER,
    budget DECIMAL(15,2)
);

CREATE TABLE roles (
    role_id INTEGER NOT NULL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL,
    access_level INTEGER DEFAULT 0
);

CREATE TABLE users (
    user_id INTEGER NOT NULL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100),
    department_id INTEGER,
    role_id INTEGER,
    salary DECIMAL(10,2),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP
);

CREATE TABLE orders (
    order_id INTEGER NOT NULL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    product_code VARCHAR(20),
    quantity INTEGER,
    unit_price DECIMAL(10,2),
    total_amount DECIMAL(12,2),
    ordered_at TIMESTAMP,
    status_code VARCHAR(20) DEFAULT 'pending'
);
