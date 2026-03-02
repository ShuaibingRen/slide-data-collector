"""Manifest validator: validates filled-in Excel manifests against schema."""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import pandas as pd

from collector.schema import load_schema, get_field_info


class ValidationError:
    """Represents a single validation error."""

    def __init__(self, row: int, field: str, message: str):
        self.row = row
        self.field = field
        self.message = message

    def __str__(self):
        return f"Row {self.row}, [{self.field}]: {self.message}"


def validate_manifest(manifest_path: str, schema_path: str) -> List[ValidationError]:
    """Validate a filled-in Excel or CSV manifest against its schema.

    Args:
        manifest_path: Path to the manifest file (.xlsx or .csv).
        schema_path: Path to the YAML schema file.

    Returns:
        List of ValidationError objects. Empty list means valid.
    """
    schema = load_schema(schema_path)
    df = _read_manifest(manifest_path)
    errors = []

    if df.empty:
        errors.append(ValidationError(0, "-", "Manifest is empty / 清单为空"))
        return errors

    # Check for missing required columns
    expected_fields = [f["name"] for f in schema["fields"]]
    for field_name in expected_fields:
        field_info = get_field_info(schema, field_name)
        if field_info and field_info.get("required") and field_name not in df.columns:
            errors.append(ValidationError(
                0, field_name,
                f"Required column missing / 缺少必填列"
            ))

    # Validate each row
    for idx, row in df.iterrows():
        row_num = idx + 3  # Excel row (1-based header + example row + 0-based index)
        for field in schema["fields"]:
            fname = field["name"]
            if fname not in df.columns:
                continue

            value = row.get(fname)
            is_empty = pd.isna(value) or str(value).strip() == ""

            # Required check
            if field.get("required") and is_empty:
                errors.append(ValidationError(
                    row_num, fname,
                    "Required field is empty / 必填字段为空"
                ))
                continue

            if is_empty:
                continue

            value_str = str(value).strip()

            # Type-specific validation
            if field["type"] == "enum":
                allowed = [str(v) for v in field["values"]]
                if value_str not in allowed:
                    errors.append(ValidationError(
                        row_num, fname,
                        f"Invalid value '{value_str}'. Allowed: {', '.join(allowed)} / "
                        f"无效值，允许的值: {', '.join(allowed)}"
                    ))

            elif field["type"] == "number":
                try:
                    float(value_str)
                except ValueError:
                    errors.append(ValidationError(
                        row_num, fname,
                        f"Expected a number, got '{value_str}' / 应为数字"
                    ))

            elif field["type"] == "date":
                if not _is_valid_date(value):
                    errors.append(ValidationError(
                        row_num, fname,
                        f"Invalid date format '{value_str}'. Use YYYY-MM-DD / "
                        f"日期格式错误，请使用 YYYY-MM-DD"
                    ))

    return errors


def _read_manifest(path: str) -> pd.DataFrame:
    """Read a manifest from Excel or CSV, skipping the example row."""
    path_obj = Path(path)
    if path_obj.suffix == ".xlsx":
        df = pd.read_excel(path, sheet_name="Data - 数据", header=0, skiprows=[1])
    elif path_obj.suffix == ".csv":
        df = pd.read_csv(path, header=0, skiprows=[1])
    else:
        raise ValueError(f"Unsupported file format: {path_obj.suffix}")
    return df


def _is_valid_date(value) -> bool:
    """Check if a value is a valid date."""
    if isinstance(value, datetime):
        return True
    if pd.isna(value):
        return False
    try:
        datetime.strptime(str(value).strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def format_errors(errors: List[ValidationError]) -> str:
    """Format validation errors for display."""
    if not errors:
        return "✅ Validation passed! / 验证通过！"

    lines = [f"❌ Found {len(errors)} error(s) / 发现 {len(errors)} 个错误:\n"]
    for err in errors:
        lines.append(f"  • {err}")
    return "\n".join(lines)
