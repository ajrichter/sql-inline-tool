"""Flexible DuckDB query system for Claude Code to query files directly."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb


class QueryEngine:
    """A flexible DuckDB query engine for inline SQL validation.

    Supports querying CSV files, Parquet files, and registered tables directly
    using SQL. Designed for use by Claude Code to perform ad-hoc analysis and
    validation of migration data.
    """

    def __init__(self, db_path: str = ":memory:"):
        """Initialize the query engine.

        Args:
            db_path: Path for DuckDB database. Defaults to in-memory.
        """
        self.conn = duckdb.connect(db_path)
        self._registered_files: dict[str, str] = {}

    def close(self) -> None:
        """Close the DuckDB connection."""
        self.conn.close()

    def register_csv(self, csv_path: str | Path, table_name: str | None = None) -> str:
        """Register a CSV file as a queryable table.

        Args:
            csv_path: Path to CSV file.
            table_name: Table name. Defaults to file stem.

        Returns:
            The table name used.
        """
        csv_path = Path(csv_path).resolve()
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        if table_name is None:
            table_name = csv_path.stem.replace("-", "_").replace(" ", "_")

        self.conn.execute(
            f"CREATE OR REPLACE VIEW {table_name} AS "
            f"SELECT * FROM read_csv_auto('{csv_path}')"
        )
        self._registered_files[table_name] = str(csv_path)
        return table_name

    def register_parquet(self, parquet_path: str | Path, table_name: str | None = None) -> str:
        """Register a Parquet file as a queryable table.

        Args:
            parquet_path: Path to Parquet file.
            table_name: Table name. Defaults to file stem.

        Returns:
            The table name used.
        """
        parquet_path = Path(parquet_path).resolve()
        if not parquet_path.exists():
            raise FileNotFoundError(f"Parquet not found: {parquet_path}")

        if table_name is None:
            table_name = parquet_path.stem.replace("-", "_").replace(" ", "_")

        self.conn.execute(
            f"CREATE OR REPLACE VIEW {table_name} AS "
            f"SELECT * FROM read_parquet('{parquet_path}')"
        )
        self._registered_files[table_name] = str(parquet_path)
        return table_name

    def register_directory(self, directory: str | Path, pattern: str = "*.csv") -> list[str]:
        """Register all matching files in a directory.

        Args:
            directory: Directory to scan.
            pattern: Glob pattern (supports *.csv and *.parquet).

        Returns:
            List of table names created.
        """
        directory = Path(directory)
        tables = []
        for path in sorted(directory.glob(pattern)):
            if path.suffix == ".csv":
                tables.append(self.register_csv(path))
            elif path.suffix == ".parquet":
                tables.append(self.register_parquet(path))
        return tables

    def query(self, sql: str) -> list[dict[str, Any]]:
        """Execute a SQL query and return results as list of dicts.

        Args:
            sql: SQL query string.

        Returns:
            List of row dicts.
        """
        result = self.conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]

    def query_df(self, sql: str):
        """Execute a SQL query and return a pandas DataFrame.

        Args:
            sql: SQL query string.

        Returns:
            pandas DataFrame with query results.
        """
        return self.conn.execute(sql).fetchdf()

    def query_arrow(self, sql: str):
        """Execute a SQL query and return a PyArrow Table.

        Args:
            sql: SQL query string.

        Returns:
            PyArrow Table with query results.
        """
        return self.conn.execute(sql).fetch_arrow_table()

    def tables(self) -> list[str]:
        """List all registered tables and views.

        Returns:
            List of table/view names.
        """
        result = self.conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main'"
        ).fetchall()
        return [row[0] for row in result]

    def describe(self, table_name: str) -> list[dict[str, Any]]:
        """Describe a table's columns and types.

        Args:
            table_name: Name of the table to describe.

        Returns:
            List of dicts with column_name, column_type, and nullable.
        """
        result = self.conn.execute(f"DESCRIBE {table_name}")
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]

    def query_file(self, sql: str, file_path: str | Path) -> list[dict[str, Any]]:
        """Query a file directly without registering it.

        The file is available in the query as 'data'.

        Args:
            sql: SQL query. Use 'data' as the table name.
            file_path: Path to CSV or Parquet file.

        Returns:
            List of row dicts.
        """
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.suffix == ".csv":
            reader = f"read_csv_auto('{file_path}')"
        elif file_path.suffix == ".parquet":
            reader = f"read_parquet('{file_path}')"
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")

        # Replace 'data' table reference with the file reader
        resolved_sql = sql.replace("data", reader, 1)
        result = self.conn.execute(resolved_sql)
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]

    def to_json(self, sql: str, pretty: bool = False) -> str:
        """Execute a query and return results as a JSON string.

        Args:
            sql: SQL query string.
            pretty: If True, format with indentation.

        Returns:
            JSON string of query results.
        """
        rows = self.query(sql)
        return json.dumps(rows, indent=2 if pretty else None, default=str)
