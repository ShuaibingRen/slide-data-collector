"""Schema loader: reads YAML schema definitions."""

import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml


def load_schema(schema_path: str) -> dict:
    """Load a YAML schema file and return its contents."""
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)
    _validate_schema_structure(schema)
    return schema


def load_all_schemas(schemas_dir: str) -> Dict[str, dict]:
    """Load all YAML schemas from a directory. Returns {type_name: schema}."""
    schemas = {}
    schemas_path = Path(schemas_dir)
    for yaml_file in sorted(schemas_path.glob("*.yaml")):
        schema = load_schema(str(yaml_file))
        type_name = yaml_file.stem  # e.g. "sample", "slide", "imaging"
        schemas[type_name] = schema
    return schemas


def get_field_names(schema: dict) -> List[str]:
    """Get ordered list of field names from schema."""
    return [f["name"] for f in schema["fields"]]


def get_required_fields(schema: dict) -> List[str]:
    """Get list of required field names."""
    return [f["name"] for f in schema["fields"] if f.get("required", False)]


def get_enum_values(schema: dict, field_name: str) -> Optional[List[str]]:
    """Get allowed enum values for a field, or None if not an enum."""
    for f in schema["fields"]:
        if f["name"] == field_name and f["type"] == "enum":
            return f.get("values", [])
    return None


def get_field_info(schema: dict, field_name: str) -> Optional[dict]:
    """Get full field definition by name."""
    for f in schema["fields"]:
        if f["name"] == field_name:
            return f
    return None


def _validate_schema_structure(schema: dict):
    """Basic validation of schema YAML structure."""
    assert "name" in schema, "Schema must have a 'name' field"
    assert "fields" in schema, "Schema must have a 'fields' list"
    assert isinstance(schema["fields"], list), "'fields' must be a list"
    for i, field in enumerate(schema["fields"]):
        assert "name" in field, f"Field #{i} missing 'name'"
        assert "type" in field, f"Field '{field['name']}' missing 'type'"
        assert field["type"] in ("string", "number", "date", "enum"), (
            f"Field '{field['name']}' has invalid type '{field['type']}'"
        )
        if field["type"] == "enum":
            assert "values" in field and len(field["values"]) > 0, (
                f"Enum field '{field['name']}' must have non-empty 'values' list"
            )
