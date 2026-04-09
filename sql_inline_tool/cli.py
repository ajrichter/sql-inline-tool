"""CLI entry point for sql-inline-tool."""

from __future__ import annotations

from pathlib import Path

import click

from sql_inline_tool.ingest import ingest_csv, ingest_csv_dir, save_parquet, checkpoint_all
from sql_inline_tool.query import QueryEngine
from sql_inline_tool.schema_converter import schema_to_csv, csv_to_schema
from sql_inline_tool.validator import InlineValidator


@click.group()
@click.version_option()
def main():
    """sql-inline-tool: Inline validation of SQL scripts using DuckDB."""


# ---------------------------------------------------------------------------
# Ingest commands
# ---------------------------------------------------------------------------

@main.command()
@click.argument("csv_path", type=click.Path(exists=True))
@click.option("--table", "-t", default=None, help="Table name (default: file stem)")
@click.option("--parquet", "-p", default=None, help="Save as Parquet checkpoint")
def ingest(csv_path: str, table: str | None, parquet: str | None):
    """Ingest a CSV file into DuckDB and optionally save as Parquet."""
    conn = ingest_csv(csv_path, table_name=table)
    table_name = table or Path(csv_path).stem.replace("-", "_").replace(" ", "_")
    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    click.echo(f"Loaded {count} rows into table '{table_name}'")

    if parquet:
        save_parquet(conn, table_name, parquet)
        click.echo(f"Saved Parquet checkpoint: {parquet}")

    conn.close()


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--output", "-o", default="checkpoints", help="Parquet output directory")
def ingest_dir(directory: str, output: str):
    """Ingest all CSVs from a directory and checkpoint as Parquet."""
    conn = ingest_csv_dir(directory)
    tables = conn.execute("SHOW TABLES").fetchall()
    for (name,) in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        click.echo(f"  {name}: {count} rows")

    paths = checkpoint_all(conn, output)
    click.echo(f"\nCheckpointed {len(paths)} tables to {output}/")
    conn.close()


# ---------------------------------------------------------------------------
# Schema conversion commands
# ---------------------------------------------------------------------------

@main.command()
@click.argument("sql_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output CSV path")
def schema2csv(sql_file: str, output: str | None):
    """Convert SQL CREATE TABLE statements to a CSV rules file."""
    sql = Path(sql_file).read_text()
    csv_content = schema_to_csv(sql, output_path=output)
    if output:
        click.echo(f"Wrote rules CSV to {output}")
    else:
        click.echo(csv_content)


@main.command()
@click.argument("csv_file", type=click.Path(exists=True))
def csv2schema(csv_file: str):
    """Convert a CSV rules file back to SQL CREATE TABLE statements."""
    sql = csv_to_schema(csv_file)
    click.echo(sql)


# ---------------------------------------------------------------------------
# Query commands
# ---------------------------------------------------------------------------

@main.command()
@click.argument("sql")
@click.option("--csv", "csv_files", multiple=True, help="CSV files to register")
@click.option("--parquet", "parquet_files", multiple=True, help="Parquet files to register")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def query(sql: str, csv_files: tuple, parquet_files: tuple, json_output: bool):
    """Run a SQL query against CSV/Parquet files."""
    engine = QueryEngine()

    for f in csv_files:
        name = engine.register_csv(f)
        click.echo(f"Registered CSV: {name}", err=True)

    for f in parquet_files:
        name = engine.register_parquet(f)
        click.echo(f"Registered Parquet: {name}", err=True)

    if json_output:
        click.echo(engine.to_json(sql, pretty=True))
    else:
        df = engine.query_df(sql)
        click.echo(df.to_string())

    engine.close()


# ---------------------------------------------------------------------------
# Validation commands
# ---------------------------------------------------------------------------

@main.command()
@click.option("--source", "-s", required=True, help="Source (pre-migration) CSV or Parquet")
@click.option("--target", "-t", required=True, help="Target (post-migration) CSV or Parquet")
@click.option("--key", "-k", multiple=True, required=True, help="Key column(s) for diff")
@click.option("--mapping", "-m", default=None, help="Mapping CSV for value validation")
@click.option("--mapping-source-col", default=None, help="Source column in mapping CSV")
@click.option("--mapping-target-col", default=None, help="Target column in mapping CSV")
@click.option("--rules", "-r", default=None, help="Validation rules CSV")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def validate(
    source: str,
    target: str,
    key: tuple,
    mapping: str | None,
    mapping_source_col: str | None,
    mapping_target_col: str | None,
    rules: str | None,
    json_output: bool,
):
    """Run inline validations comparing source and target data."""
    engine = QueryEngine()
    validator = InlineValidator(engine)

    # Register source and target
    src_name = _register_file(engine, source, "source")
    tgt_name = _register_file(engine, target, "target")

    # Run standard checks
    validator.check_row_count(src_name, tgt_name)
    validator.check_schema_compatibility(src_name, tgt_name)
    validator.diff_tables(src_name, tgt_name, key_columns=list(key))

    # Mapping validation
    if mapping and mapping_source_col and mapping_target_col:
        map_name = _register_file(engine, mapping, "mapping")
        validator.check_mapping(
            tgt_name, map_name, mapping_source_col, mapping_target_col
        )

    # Custom rules
    if rules:
        validator.run_validation_suite(rules)

    # Output
    report = validator.report
    if json_output:
        click.echo(report.to_json())
    else:
        click.echo(report.summary())
        for r in report.results:
            icon = "PASS" if r.status.value == "PASS" else "FAIL" if r.status.value == "FAIL" else "ERR "
            click.echo(f"  [{icon}] {r.name}: {r.message}")

    engine.close()
    raise SystemExit(0 if report.all_passed else 1)


def _register_file(engine: QueryEngine, path: str, default_name: str) -> str:
    """Register a CSV or Parquet file with the engine."""
    p = Path(path)
    if p.suffix == ".parquet":
        return engine.register_parquet(p, default_name)
    else:
        return engine.register_csv(p, default_name)
