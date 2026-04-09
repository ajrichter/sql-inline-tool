CREATE TABLE employees (
    id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    department_code VARCHAR(50) NOT NULL,
    salary DECIMAL(10,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE departments (
    code VARCHAR(50) NOT NULL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    budget DECIMAL(15,2),
    head_count INTEGER DEFAULT 0
);
