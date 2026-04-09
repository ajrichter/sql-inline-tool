"""CSV ingestion into DuckDB with Parquet checkpoint support."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb


def ingest_csv(
    csv_path: str | Path,
    table_name: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
    schema: str | None = None,
) -> duckdb.DuckDBPyConnection:
    """Load a CSV file into a DuckDB table.

    Args:
        csv_path: Path to the CSV file.
        table_name: Name for the DuckDB table. Defaults to the CSV filename stem.
        conn: Existing DuckDB connection. Creates in-memory if None.
        schema: Optional SQL column definitions to override auto-detection.
            e.g. "id INTEGER, name VARCHAR, amount DECIMAL(10,2)"

    Returns:
        The DuckDB connection with the table loaded.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    if table_name is None:
        table_name = csv_path.stem.replace("-", "_").replace(" ", "_")

    if conn is None:
        conn = duckdb.connect(":memory:")

    if schema:
        conn.execute(f"CREATE TABLE {table_name} ({schema})")
        conn.execute(
            f"COPY {table_name} FROM '{csv_path}' (HEADER true, AUTO_DETECT false)"
        )
    else:
        conn.execute(
            f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{csv_path}')"
        )

    return conn


def ingest_csv_dir(
    directory: str | Path,
    conn: duckdb.DuckDBPyConnection | None = None,
    glob_pattern: str = "*.csv",
) -> duckdb.DuckDBPyConnection:
    """Load all CSV files from a directory into DuckDB tables.

    Each CSV becomes a table named after the file stem.

    Args:
        directory: Directory containing CSV files.
        conn: Existing DuckDB connection. Creates in-memory if None.
        glob_pattern: Glob pattern for CSV files.

    Returns:
        The DuckDB connection with all tables loaded.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    if conn is None:
        conn = duckdb.connect(":memory:")

    csv_files = sorted(directory.glob(glob_pattern))
    if not csv_files:
        raise FileNotFoundError(f"No files matching '{glob_pattern}' in {directory}")

    for csv_file in csv_files:
        ingest_csv(csv_file, conn=conn)

    return conn


def save_parquet(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    output_path: str | Path,
) -> Path:
    """Save a DuckDB table as a Parquet checkpoint file.

    Args:
        conn: DuckDB connection containing the table.
        table_name: Name of the table to export.
        output_path: Path for the output Parquet file.

    Returns:
        Path to the created Parquet file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(f"COPY {table_name} TO '{output_path}' (FORMAT PARQUET)")
    return output_path


def load_parquet(
    parquet_path: str | Path,
    table_name: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> duckdb.DuckDBPyConnection:
    """Load a Parquet checkpoint file into a DuckDB table.

    Args:
        parquet_path: Path to the Parquet file.
        table_name: Name for the DuckDB table. Defaults to the file stem.
        conn: Existing DuckDB connection. Creates in-memory if None.

    Returns:
        The DuckDB connection with the table loaded.
    """
    parquet_path = Path(parquet_path)
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

    if table_name is None:
        table_name = parquet_path.stem.replace("-", "_").replace(" ", "_")

    if conn is None:
        conn = duckdb.connect(":memory:")

    conn.execute(
        f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet('{parquet_path}')"
    )
    return conn


def checkpoint_all(
    conn: duckdb.DuckDBPyConnection,
    output_dir: str | Path,
) -> list[Path]:
    """Save all tables in a DuckDB connection as Parquet checkpoint files.

    Args:
        conn: DuckDB connection with tables to export.
        output_dir: Directory to write Parquet files into.

    Returns:
        List of paths to created Parquet files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tables = conn.execute("SHOW TABLES").fetchall()
    paths = []
    for (table_name,) in tables:
        path = save_parquet(conn, table_name, output_dir / f"{table_name}.parquet")
        paths.append(path)
    return paths
