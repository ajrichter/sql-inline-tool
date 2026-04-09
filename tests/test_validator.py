"""Tests for the inline validator."""

from pathlib import Path

import pytest

from sql_inline_tool.query import QueryEngine
from sql_inline_tool.validator import InlineValidator, ValidationStatus

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture
def setup():
    engine = QueryEngine()
    engine.register_csv(EXAMPLES / "source_data.csv", "source")
    engine.register_csv(EXAMPLES / "target_data.csv", "target")
    engine.register_csv(EXAMPLES / "department_mapping.csv", "mapping")
    validator = InlineValidator(engine)
    yield engine, validator
    engine.close()


def test_check_row_count(setup):
    engine, validator = setup
    result = validator.check_row_count("source", "target")
    assert result.status == ValidationStatus.PASS


def test_check_row_count_mismatch(setup):
    engine, validator = setup
    engine.conn.execute("CREATE TABLE small AS SELECT * FROM source LIMIT 2")
    result = validator.check_row_count("source", "small", name="count_mismatch")
    assert result.status == ValidationStatus.FAIL


def test_check_schema_compatibility(setup):
    engine, validator = setup
    result = validator.check_schema_compatibility("source", "target")
    assert result.status == ValidationStatus.PASS


def test_check_mapping(setup):
    engine, validator = setup
    result = validator.check_mapping(
        "target", "mapping", "old_code", "new_code",
        data_col="department_code", name="dept_mapping",
    )
    assert result.status == ValidationStatus.PASS


def test_check_sql_pass(setup):
    engine, validator = setup
    result = validator.check_sql(
        "SELECT * FROM target WHERE id IS NULL",
        name="no_nulls",
    )
    assert result.status == ValidationStatus.PASS


def test_check_sql_fail(setup):
    engine, validator = setup
    result = validator.check_sql(
        "SELECT * FROM target WHERE status = 'active'",
        name="expect_no_active",
    )
    assert result.status == ValidationStatus.FAIL


def test_diff_tables(setup):
    engine, validator = setup
    result = validator.diff_tables(
        "source", "target", key_columns=["id"], compare_columns=["name", "salary", "status"]
    )
    # names, salary, and status are the same → should pass
    assert result.status == ValidationStatus.PASS


def test_diff_tables_detects_changes(setup):
    engine, validator = setup
    result = validator.diff_tables(
        "source", "target", key_columns=["id"], compare_columns=["department_code"]
    )
    # department_code changed from short to long form → should fail
    assert result.status == ValidationStatus.FAIL


def test_report_summary(setup):
    _, validator = setup
    validator.check_row_count("source", "target")
    validator.check_schema_compatibility("source", "target")
    summary = validator.report.summary()
    assert "2/2 passed" in summary


def test_report_json(setup):
    _, validator = setup
    validator.check_row_count("source", "target")
    j = validator.report.to_json()
    assert '"PASS"' in j


def test_validation_suite(setup):
    engine, validator = setup
    report = validator.run_validation_suite(EXAMPLES / "validation_rules.csv")
    assert len(report.results) >= 4
