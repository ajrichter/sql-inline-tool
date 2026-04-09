"""Tests for CSV ingestion and Parquet checkpointing."""

import tempfile
from pathlib import Path

import duckdb
import pytest

from sql_inline_tool.ingest import (
    ingest_csv,
    ingest_csv_dir,
    save_parquet,
    load_parquet,
    checkpoint_all,
)

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_ingest_csv():
    conn = ingest_csv(EXAMPLES / "source_data.csv")
    rows = conn.execute("SELECT COUNT(*) FROM source_data").fetchone()[0]
    assert rows == 5
    conn.close()


def test_ingest_csv_custom_table():
    conn = ingest_csv(EXAMPLES / "source_data.csv", table_name="employees")
    rows = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    assert rows == 5
    conn.close()


def test_ingest_csv_not_found():
    with pytest.raises(FileNotFoundError):
        ingest_csv("nonexistent.csv")


def test_ingest_csv_dir():
    conn = ingest_csv_dir(EXAMPLES, glob_pattern="*_data.csv")
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    assert "source_data" in tables
    assert "target_data" in tables
    conn.close()


def test_save_and_load_parquet():
    conn = ingest_csv(EXAMPLES / "source_data.csv")

    with tempfile.TemporaryDirectory() as tmpdir:
        pq_path = save_parquet(conn, "source_data", Path(tmpdir) / "test.parquet")
        assert pq_path.exists()

        conn2 = load_parquet(pq_path, "loaded")
        rows = conn2.execute("SELECT COUNT(*) FROM loaded").fetchone()[0]
        assert rows == 5
        conn2.close()

    conn.close()


def test_checkpoint_all():
    conn = ingest_csv_dir(EXAMPLES, glob_pattern="*_data.csv")

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = checkpoint_all(conn, tmpdir)
        assert len(paths) >= 2
        for p in paths:
            assert p.exists()
            assert p.suffix == ".parquet"

    conn.close()
