"""Tests for the query engine."""

from pathlib import Path

import pytest

from sql_inline_tool.query import QueryEngine

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture
def engine():
    e = QueryEngine()
    yield e
    e.close()


def test_register_csv(engine):
    name = engine.register_csv(EXAMPLES / "source_data.csv")
    assert name == "source_data"
    assert "source_data" in engine.tables()


def test_query(engine):
    engine.register_csv(EXAMPLES / "source_data.csv")
    rows = engine.query("SELECT * FROM source_data WHERE status = 'active'")
    assert len(rows) == 4
    assert all(r["status"] == "active" for r in rows)


def test_query_df(engine):
    engine.register_csv(EXAMPLES / "source_data.csv")
    df = engine.query_df("SELECT * FROM source_data")
    assert len(df) == 5
    assert "name" in df.columns


def test_describe(engine):
    engine.register_csv(EXAMPLES / "source_data.csv")
    desc = engine.describe("source_data")
    col_names = [d["column_name"] for d in desc]
    assert "id" in col_names
    assert "name" in col_names


def test_to_json(engine):
    engine.register_csv(EXAMPLES / "source_data.csv")
    j = engine.to_json("SELECT COUNT(*) as cnt FROM source_data")
    assert '"cnt"' in j


def test_register_directory(engine):
    tables = engine.register_directory(EXAMPLES, pattern="*_data.csv")
    assert "source_data" in tables
    assert "target_data" in tables


def test_register_csv_not_found(engine):
    with pytest.raises(FileNotFoundError):
        engine.register_csv("nonexistent.csv")
