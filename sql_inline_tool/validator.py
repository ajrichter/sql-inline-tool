"""Inline validation engine for comparing pre- and post-migration SQL outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any

import duckdb

from sql_inline_tool.query import QueryEngine


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    name: str
    status: ValidationStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class ValidationReport:
    """Aggregate report of all validation checks."""
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.FAIL)

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.ERROR)

    @property
    def all_passed(self) -> bool:
        return all(r.status == ValidationStatus.PASS for r in self.results)

    def summary(self) -> str:
        total = len(self.results)
        return (
            f"Validation: {self.passed}/{total} passed, "
            f"{self.failed} failed, {self.errors} errors"
        )

    def to_json(self, pretty: bool = True) -> str:
        return json.dumps(
            {
                "summary": self.summary(),
                "all_passed": self.all_passed,
                "results": [r.to_dict() for r in self.results],
            },
            indent=2 if pretty else None,
            default=str,
        )


class InlineValidator:
    """Validates SQL migration outputs by comparing pre- and post-migration data.

    Supports:
    - Row count comparisons
    - Schema compatibility checks
    - Value mapping validations using CSV rule files
    - Custom SQL assertion checks
    - Diff queries between two datasets
    """

    def __init__(self, engine: QueryEngine | None = None):
        self.engine = engine or QueryEngine()
        self.report = ValidationReport()

    def check_row_count(
        self,
        source_table: str,
        target_table: str,
        name: str = "row_count",
        allow_growth: bool = False,
    ) -> ValidationResult:
        """Validate that row counts match between source and target tables.

        Args:
            source_table: Pre-migration table name.
            target_table: Post-migration table name.
            name: Name for this check.
            allow_growth: If True, target may have more rows than source.
        """
        try:
            src_count = self.engine.query(f"SELECT COUNT(*) as cnt FROM {source_table}")[0]["cnt"]
            tgt_count = self.engine.query(f"SELECT COUNT(*) as cnt FROM {target_table}")[0]["cnt"]

            if src_count == tgt_count:
                result = ValidationResult(
                    name=name,
                    status=ValidationStatus.PASS,
                    message=f"Row counts match: {src_count}",
                    details={"source": src_count, "target": tgt_count},
                )
            elif allow_growth and tgt_count > src_count:
                result = ValidationResult(
                    name=name,
                    status=ValidationStatus.PASS,
                    message=f"Target has more rows ({tgt_count} vs {src_count}), growth allowed",
                    details={"source": src_count, "target": tgt_count},
                )
            else:
                result = ValidationResult(
                    name=name,
                    status=ValidationStatus.FAIL,
                    message=f"Row count mismatch: source={src_count}, target={tgt_count}",
                    details={"source": src_count, "target": tgt_count},
                )
        except Exception as e:
            result = ValidationResult(
                name=name,
                status=ValidationStatus.ERROR,
                message=str(e),
            )

        self.report.results.append(result)
        return result

    def check_schema_compatibility(
        self,
        source_table: str,
        target_table: str,
        name: str = "schema_compat",
    ) -> ValidationResult:
        """Check that the target table has all columns from the source.

        Args:
            source_table: Pre-migration table name.
            target_table: Post-migration table name.
            name: Name for this check.
        """
        try:
            src_cols = {r["column_name"] for r in self.engine.describe(source_table)}
            tgt_cols = {r["column_name"] for r in self.engine.describe(target_table)}

            missing = src_cols - tgt_cols
            added = tgt_cols - src_cols

            if not missing:
                result = ValidationResult(
                    name=name,
                    status=ValidationStatus.PASS,
                    message="All source columns present in target",
                    details={"missing": [], "added": list(added)},
                )
            else:
                result = ValidationResult(
                    name=name,
                    status=ValidationStatus.FAIL,
                    message=f"Missing columns in target: {missing}",
                    details={"missing": list(missing), "added": list(added)},
                )
        except Exception as e:
            result = ValidationResult(
                name=name,
                status=ValidationStatus.ERROR,
                message=str(e),
            )

        self.report.results.append(result)
        return result

    def check_mapping(
        self,
        table_name: str,
        mapping_table: str,
        source_col: str,
        target_col: str,
        data_col: str | None = None,
        name: str = "mapping_check",
    ) -> ValidationResult:
        """Validate that values in a column match an expected mapping.

        The mapping_table should have columns with old→new value mappings.

        Args:
            table_name: Table containing the data to validate.
            mapping_table: Table with the expected mappings.
            source_col: Column name for old values in the mapping table.
            target_col: Column name for new values in the mapping table.
            data_col: Column in table_name to check. Defaults to target_col.
            name: Name for this check.
        """
        if data_col is None:
            data_col = target_col
        try:
            unmatched = self.engine.query(f"""
                SELECT t.{data_col}, COUNT(*) as cnt
                FROM {table_name} t
                LEFT JOIN {mapping_table} m ON t.{data_col} = m.{target_col}
                WHERE m.{target_col} IS NULL
                GROUP BY t.{data_col}
            """)

            if not unmatched:
                result = ValidationResult(
                    name=name,
                    status=ValidationStatus.PASS,
                    message="All values match the mapping",
                )
            else:
                result = ValidationResult(
                    name=name,
                    status=ValidationStatus.FAIL,
                    message=f"{len(unmatched)} unmapped values found",
                    details={"unmatched": unmatched},
                )
        except Exception as e:
            result = ValidationResult(
                name=name,
                status=ValidationStatus.ERROR,
                message=str(e),
            )

        self.report.results.append(result)
        return result

    def check_sql(
        self,
        sql: str,
        name: str = "custom_check",
        expect_empty: bool = True,
    ) -> ValidationResult:
        """Run a custom SQL assertion.

        By default, the check passes if the query returns no rows (i.e., no
        violations found). Set expect_empty=False to pass when rows ARE returned.

        Args:
            sql: SQL query to run.
            name: Name for this check.
            expect_empty: If True, pass when query returns 0 rows.
        """
        try:
            rows = self.engine.query(sql)
            is_empty = len(rows) == 0

            if is_empty == expect_empty:
                result = ValidationResult(
                    name=name,
                    status=ValidationStatus.PASS,
                    message=f"Assertion passed ({len(rows)} rows returned)",
                    details={"row_count": len(rows)},
                )
            else:
                result = ValidationResult(
                    name=name,
                    status=ValidationStatus.FAIL,
                    message=f"Assertion failed ({len(rows)} rows returned)",
                    details={"row_count": len(rows), "sample": rows[:10]},
                )
        except Exception as e:
            result = ValidationResult(
                name=name,
                status=ValidationStatus.ERROR,
                message=str(e),
            )

        self.report.results.append(result)
        return result

    def diff_tables(
        self,
        source_table: str,
        target_table: str,
        key_columns: list[str],
        compare_columns: list[str] | None = None,
        name: str = "diff",
    ) -> ValidationResult:
        """Find differences between source and target tables.

        Args:
            source_table: Pre-migration table.
            target_table: Post-migration table.
            key_columns: Columns that uniquely identify a row.
            compare_columns: Columns to compare. If None, compares all shared columns.
            name: Name for this check.
        """
        try:
            if compare_columns is None:
                src_cols = {r["column_name"] for r in self.engine.describe(source_table)}
                tgt_cols = {r["column_name"] for r in self.engine.describe(target_table)}
                compare_columns = list(src_cols & tgt_cols - set(key_columns))

            if not compare_columns:
                result = ValidationResult(
                    name=name,
                    status=ValidationStatus.PASS,
                    message="No comparable columns found (key-only tables match by definition)",
                )
                self.report.results.append(result)
                return result

            key_join = " AND ".join(f"s.{k} = t.{k}" for k in key_columns)
            diff_conditions = " OR ".join(
                f"s.{c} IS DISTINCT FROM t.{c}" for c in compare_columns
            )
            key_select = ", ".join(f"COALESCE(s.{k}, t.{k}) as {k}" for k in key_columns)
            diff_detail = ", ".join(
                f"s.{c} as src_{c}, t.{c} as tgt_{c}" for c in compare_columns
            )

            sql = f"""
                SELECT {key_select}, {diff_detail}
                FROM {source_table} s
                FULL OUTER JOIN {target_table} t ON {key_join}
                WHERE {diff_conditions}
                   OR s.{key_columns[0]} IS NULL
                   OR t.{key_columns[0]} IS NULL
                LIMIT 100
            """

            diffs = self.engine.query(sql)

            if not diffs:
                result = ValidationResult(
                    name=name,
                    status=ValidationStatus.PASS,
                    message="No differences found",
                )
            else:
                result = ValidationResult(
                    name=name,
                    status=ValidationStatus.FAIL,
                    message=f"{len(diffs)} differences found (showing up to 100)",
                    details={"differences": diffs},
                )
        except Exception as e:
            result = ValidationResult(
                name=name,
                status=ValidationStatus.ERROR,
                message=str(e),
            )

        self.report.results.append(result)
        return result

    def run_validation_suite(
        self,
        rules_csv: str | Path,
    ) -> ValidationReport:
        """Run a suite of validations defined in a CSV rules file.

        The CSV should have columns: name, type, sql, expect_empty

        Supported rule types:
        - sql_assertion: Runs a SQL query; passes if result is empty (or not, per expect_empty)

        Args:
            rules_csv: Path to the CSV rules file.

        Returns:
            The ValidationReport with all results.
        """
        rules_csv = Path(rules_csv)
        rules = self.engine.query(
            f"SELECT * FROM read_csv_auto('{rules_csv}')"
        )

        for rule in rules:
            rule_type = rule.get("type", "sql_assertion")
            name = rule.get("name", "unnamed_rule")
            sql = rule.get("sql", "")
            expect_empty = str(rule.get("expect_empty", "true")).lower() == "true"

            if rule_type == "sql_assertion":
                self.check_sql(sql, name=name, expect_empty=expect_empty)

        return self.report
