"""Mini test suite — runs DuckDB SQL directly to verify everything works."""

import duckdb
import sys


def run_test(name, conn, sql, expect_rows=None, expect_pass=True):
    """Run a SQL test and report result."""
    try:
        result = conn.execute(sql).fetchall()
        if expect_rows is not None and len(result) != expect_rows:
            print(f"  FAIL  {name}: expected {expect_rows} rows, got {len(result)}")
            return False
        print(f"  PASS  {name}")
        return True
    except Exception as e:
        print(f"  ERROR {name}: {e}")
        return False


def main():
    conn = duckdb.connect(":memory:")
    results = []

    print("=== CSV Ingestion ===")
    results.append(run_test(
        "load source CSV",
        conn,
        "CREATE TABLE source_data AS SELECT * FROM read_csv_auto('examples/source_data.csv')",
    ))
    results.append(run_test(
        "source has 5 rows",
        conn,
        "SELECT * FROM source_data",
        expect_rows=5,
    ))
    results.append(run_test(
        "load target CSV",
        conn,
        "CREATE TABLE target_data AS SELECT * FROM read_csv_auto('examples/target_data.csv')",
    ))
    results.append(run_test(
        "load mapping CSV",
        conn,
        "CREATE TABLE mapping AS SELECT * FROM read_csv_auto('examples/department_mapping.csv')",
    ))

    print("\n=== Parquet Checkpoint ===")
    conn.execute("COPY source_data TO '/tmp/test_source.parquet' (FORMAT PARQUET)")
    results.append(run_test(
        "roundtrip through parquet",
        conn,
        "SELECT * FROM read_parquet('/tmp/test_source.parquet')",
        expect_rows=5,
    ))

    print("\n=== Schema Extraction ===")
    results.append(run_test(
        "extract schema info",
        conn,
        """SELECT table_name, column_name, data_type
           FROM information_schema.columns
           WHERE table_schema = 'main' AND table_name = 'source_data'""",
        expect_rows=5,
    ))

    print("\n=== Direct File Queries ===")
    results.append(run_test(
        "query CSV directly",
        conn,
        "SELECT * FROM read_csv_auto('examples/source_data.csv') WHERE status = 'active'",
        expect_rows=4,
    ))
    results.append(run_test(
        "join two CSV files directly",
        conn,
        """SELECT s.name, m.new_code
           FROM read_csv_auto('examples/source_data.csv') s
           JOIN read_csv_auto('examples/department_mapping.csv') m
               ON s.department_code = m.old_code""",
        expect_rows=5,
    ))

    print("\n=== Inline Validations ===")
    results.append(run_test(
        "row counts match",
        conn,
        """SELECT 1 WHERE (SELECT COUNT(*) FROM source_data) =
                          (SELECT COUNT(*) FROM target_data)""",
        expect_rows=1,
    ))
    results.append(run_test(
        "no NULL IDs in target",
        conn,
        "SELECT * FROM target_data WHERE id IS NULL",
        expect_rows=0,
    ))
    results.append(run_test(
        "no duplicate IDs in target",
        conn,
        "SELECT id FROM target_data GROUP BY id HAVING COUNT(*) > 1",
        expect_rows=0,
    ))
    results.append(run_test(
        "all target depts mapped",
        conn,
        """SELECT DISTINCT t.department_code
           FROM target_data t
           LEFT JOIN mapping m ON t.department_code = m.new_code
           WHERE m.new_code IS NULL""",
        expect_rows=0,
    ))
    results.append(run_test(
        "no data loss (source IDs in target)",
        conn,
        """SELECT s.id FROM source_data s
           LEFT JOIN target_data t ON s.id = t.id
           WHERE t.id IS NULL""",
        expect_rows=0,
    ))
    results.append(run_test(
        "mapping applied correctly",
        conn,
        """SELECT s.id
           FROM source_data s
           JOIN mapping m ON s.department_code = m.old_code
           JOIN target_data t ON s.id = t.id
           WHERE t.department_code != m.new_code""",
        expect_rows=0,
    ))
    results.append(run_test(
        "diff detects dept_code changes",
        conn,
        """SELECT s.id
           FROM source_data s
           JOIN target_data t ON s.id = t.id
           WHERE s.department_code IS DISTINCT FROM t.department_code""",
        expect_rows=5,
    ))
    results.append(run_test(
        "non-dept values unchanged",
        conn,
        """SELECT s.id
           FROM source_data s
           JOIN target_data t ON s.id = t.id
           WHERE s.name IS DISTINCT FROM t.name
              OR s.salary IS DISTINCT FROM t.salary
              OR s.status IS DISTINCT FROM t.status""",
        expect_rows=0,
    ))

    conn.close()

    passed = sum(results)
    total = len(results)
    print(f"\n{'='*40}")
    print(f"Results: {passed}/{total} passed")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
