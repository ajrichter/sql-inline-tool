-- ============================================================
-- OLD SCHEMA (pre-migration)
-- ============================================================

CREATE TABLE users (
    user_id INTEGER NOT NULL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100),
    dept_code VARCHAR(10),
    role_id INTEGER,
    salary DECIMAL(10,2),
    is_active INTEGER DEFAULT 1,
    created_date VARCHAR(20)
);

CREATE TABLE departments (
    dept_code VARCHAR(10) NOT NULL PRIMARY KEY,
    dept_name VARCHAR(100) NOT NULL,
    manager_id INTEGER,
    budget DECIMAL(15,2)
);

CREATE TABLE roles (
    role_id INTEGER NOT NULL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL,
    access_level INTEGER DEFAULT 0
);

CREATE TABLE orders (
    order_id INTEGER NOT NULL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    product_code VARCHAR(20),
    quantity INTEGER,
    unit_price DECIMAL(10,2),
    order_date VARCHAR(20),
    status VARCHAR(10) DEFAULT 'pending'
);
