"""Tests for SQL schema to CSV conversion."""

from pathlib import Path

from sql_inline_tool.schema_converter import parse_create_table, schema_to_csv, csv_to_schema

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_parse_create_table():
    sql = (EXAMPLES / "schema.sql").read_text()
    rules = parse_create_table(sql)
    assert len(rules) > 0

    # Check employees table parsed
    emp_rules = [r for r in rules if r["table"] == "employees"]
    assert len(emp_rules) == 5

    id_rule = next(r for r in emp_rules if r["column"] == "id")
    assert id_rule["data_type"] == "INTEGER"
    assert id_rule["nullable"] is False


def test_schema_to_csv():
    sql = (EXAMPLES / "schema.sql").read_text()
    csv_content = schema_to_csv(sql)
    assert "table,column,data_type" in csv_content
    assert "employees" in csv_content
    assert "departments" in csv_content


def test_schema_to_csv_file(tmp_path):
    sql = (EXAMPLES / "schema.sql").read_text()
    out = tmp_path / "rules.csv"
    schema_to_csv(sql, output_path=out)
    assert out.exists()
    assert "employees" in out.read_text()


def test_csv_to_schema(tmp_path):
    sql = (EXAMPLES / "schema.sql").read_text()
    csv_path = tmp_path / "rules.csv"
    schema_to_csv(sql, output_path=csv_path)

    reconstructed = csv_to_schema(csv_path)
    assert "CREATE TABLE employees" in reconstructed
    assert "CREATE TABLE departments" in reconstructed
