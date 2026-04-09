"""Convert SQL schema definitions to CSV rule files and vice versa."""

from __future__ import annotations

import csv
import re
from io import StringIO
from pathlib import Path

import duckdb


def parse_create_table(sql: str) -> list[dict]:
    """Parse CREATE TABLE statements and extract column rules.

    Args:
        sql: SQL string containing one or more CREATE TABLE statements.

    Returns:
        List of dicts with keys: table, column, data_type, nullable, default, constraints.
    """
    rules = []
    # Match CREATE TABLE blocks
    pattern = re.compile(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"(\S+)\s*\((.*?)\)\s*;",
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(sql):
        table_name = match.group(1).strip('"').strip("'").strip("`")
        body = match.group(2)

        # Split on commas that are not inside parentheses
        columns = _split_columns(body)

        for col_def in columns:
            col_def = col_def.strip()
            if not col_def:
                continue

            # Skip table-level constraints
            upper = col_def.upper().lstrip()
            if upper.startswith(("PRIMARY KEY", "UNIQUE", "CHECK", "FOREIGN KEY", "CONSTRAINT")):
                continue

            parsed = _parse_column_def(table_name, col_def)
            if parsed:
                rules.append(parsed)

    return rules


def _split_columns(body: str) -> list[str]:
    """Split column definitions respecting parenthesized expressions."""
    parts = []
    depth = 0
    current = []
    for char in body:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def _parse_column_def(table_name: str, col_def: str) -> dict | None:
    """Parse a single column definition into a rule dict."""
    tokens = col_def.split()
    if len(tokens) < 2:
        return None

    col_name = tokens[0].strip('"').strip("'").strip("`")
    rest = " ".join(tokens[1:])

    # Extract data type (first token or tokens with parentheses)
    type_match = re.match(r"(\w+(?:\([^)]*\))?)", rest)
    data_type = type_match.group(1) if type_match else tokens[1]

    nullable = "NOT NULL" not in rest.upper()
    default = None
    default_match = re.search(r"DEFAULT\s+(\S+)", rest, re.IGNORECASE)
    if default_match:
        default = default_match.group(1).strip("'\"")

    # Collect remaining constraints
    constraints = []
    if "PRIMARY KEY" in rest.upper():
        constraints.append("PRIMARY KEY")
    if "UNIQUE" in rest.upper():
        constraints.append("UNIQUE")
    check_match = re.search(r"(CHECK\s*\([^)]+\))", rest, re.IGNORECASE)
    if check_match:
        constraints.append(check_match.group(1))

    return {
        "table": table_name,
        "column": col_name,
        "data_type": data_type,
        "nullable": nullable,
        "default": default,
        "constraints": "; ".join(constraints) if constraints else None,
    }


def schema_to_csv(sql: str, output_path: str | Path | None = None) -> str:
    """Convert SQL CREATE TABLE statements to a CSV rules file.

    Args:
        sql: SQL string with CREATE TABLE statements.
        output_path: Optional file path to write the CSV. If None, returns CSV string.

    Returns:
        The CSV content as a string.
    """
    rules = parse_create_table(sql)
    if not rules:
        raise ValueError("No CREATE TABLE statements found in the SQL input")

    fieldnames = ["table", "column", "data_type", "nullable", "default", "constraints"]
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rules)

    csv_content = output.getvalue()

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(csv_content)

    return csv_content


def csv_to_schema(csv_path: str | Path) -> str:
    """Convert a CSV rules file back into SQL CREATE TABLE statements.

    Args:
        csv_path: Path to the CSV rules file.

    Returns:
        SQL string with CREATE TABLE statements.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Group by table
    tables: dict[str, list[dict]] = {}
    for row in rows:
        tables.setdefault(row["table"], []).append(row)

    statements = []
    for table_name, columns in tables.items():
        col_defs = []
        for col in columns:
            parts = [f"  {col['column']} {col['data_type']}"]
            if col.get("nullable", "").lower() == "false":
                parts.append("NOT NULL")
            if col.get("default"):
                parts.append(f"DEFAULT {col['default']}")
            if col.get("constraints"):
                parts.append(col["constraints"].replace("; ", " "))
            col_defs.append(" ".join(parts))

        stmt = f"CREATE TABLE {table_name} (\n" + ",\n".join(col_defs) + "\n);"
        statements.append(stmt)

    return "\n\n".join(statements)
