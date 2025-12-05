#!/usr/bin/env python3
"""
Convert data-model.xlsx to JSON Schema.

Reads the Excel file from dat/data-model/incoming/data-model.xlsx
and generates a JSON Schema based on the column definitions.

The xlsx is the authoritative source for:
- Field names, descriptions, datatypes, multiplicity
- Required tier (trigger, generated, defaulted, enriched)
- Default values
- Valid values (enums)

Features:
- Nested structures using dot notation (e.g., "Record.SourceSystem" -> record.sourceSystem)
- Array support with bracket notation (e.g., "ServicePoint[].Id")
- Format constraints for dates, emails, etc.
- $ref usage for reusable patterns (IBAN, BIC, phone, etc.)
- x-tier extension to mark field tiers
- Enums read from xlsx "Valid Values" column
- Defaults read from xlsx "Default Value" column
- SEPA conditional: trigger data is implicitly SEPA (method absent or SEPA_DIRECT_DEBIT)
- additionalProperties: false for strict validation
"""

import json
import re
from pathlib import Path

from openpyxl import load_workbook

# Hardcoded paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
INPUT_FILE = PROJECT_ROOT / "dat" / "data-model" / "incoming" / "data-model.xlsx"
OUTPUT_FILE = PROJECT_ROOT / "dat" / "data-model" / "incoming" / "data-model.schema.json"

# Current sheet version
SHEET_NAME = "v0.2"

# Schema ID for versioning
SCHEMA_ID = "https://example.com/schemas/data-model/v1.0.0"

# Known formats based on field names or datatype hints
FORMAT_HINTS = {
    "createdat": "date-time",
    "updatedat": "date-time",
    "dateofbirth": "date",
    "mandatesignaturedate": "date",
    "email": "email",
}

# Patterns for specific field types - maps field name pattern to $def name
PATTERN_REFS = {
    "iban": "iban",
    "bic": "bic",
    "countrycode": "countryCode",
    "currency": "currencyCode",
    "phone": "phoneNumber",
    "postalcode": "postalCode",
    "timezone": "timezone",
}

# $defs definitions
DEFS = {
    "iban": {
        "type": "string",
        "pattern": r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{4,30}$",
        "description": "International Bank Account Number (IBAN)",
    },
    "bic": {
        "type": "string",
        "pattern": r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$",
        "description": "Bank Identifier Code (BIC/SWIFT)",
    },
    "countryCode": {
        "type": "string",
        "pattern": r"^[A-Z]{2}$",
        "description": "ISO 3166-1 alpha-2 country code",
    },
    "currencyCode": {
        "type": "string",
        "pattern": r"^[A-Z]{3}$",
        "description": "ISO 4217 three-letter currency code",
    },
    "phoneNumber": {
        "type": "string",
        "pattern": r"^\+?[0-9\s\-\(\)]{6,20}$",
        "description": "Phone number in international or local format",
    },
    "postalCode": {
        "type": "string",
        "pattern": r"^[A-Z0-9\-\s]{3,10}$",
        "description": "Postal/ZIP code",
    },
    "timezone": {
        "type": "string",
        "pattern": r"^[A-Za-z]+(?:_[A-Za-z]+)?/[A-Za-z0-9_+-]+$",
        "description": "IANA timezone identifier (e.g., Europe/Berlin)",
    },
}


def map_datatype(
    datatype: str,
    field_name: str = "",
    valid_values: str = "",
    default_value: str = "",
    required_tier: str = "",
) -> dict:
    """Map Excel datatype to JSON Schema type with format hints."""
    datatype_raw = datatype.lower().strip() if datatype else "string"
    field_lower = field_name.lower()

    # Handle parameterized types like string(datetime), string(date), string(2)
    base_type = datatype_raw
    param = None
    if "(" in datatype_raw:
        match = re.match(r"(\w+)\(([^)]+)\)", datatype_raw)
        if match:
            base_type = match.group(1)
            param = match.group(2)

    type_mapping = {
        "string": {"type": "string"},
        "str": {"type": "string"},
        "integer": {"type": "integer"},
        "int": {"type": "integer"},
        "number": {"type": "number"},
        "float": {"type": "number"},
        "boolean": {"type": "boolean"},
        "bool": {"type": "boolean"},
        "array": {"type": "array"},
        "object": {"type": "object"},
        "enum": {"type": "string"},
    }

    # Check if field should use $ref (exact match or ends with pattern)
    ref_name = None
    for pattern_key, def_name in PATTERN_REFS.items():
        # Match: "postalcode" or "address.postalcode" but not "postalcodeisvalid"
        if field_lower == pattern_key or field_lower.endswith(f".{pattern_key}"):
            ref_name = def_name
            break

    if ref_name:
        # Use $ref with allOf to allow adding description and other properties
        result = {"allOf": [{"$ref": f"#/$defs/{ref_name}"}]}
    else:
        result = type_mapping.get(base_type, {"type": "string"}).copy()

        # Apply format from parameter
        if param in ("datetime", "date-time"):
            result["format"] = "date-time"
        elif param == "date":
            result["format"] = "date"
        elif param and param.isdigit():
            result["maxLength"] = int(param)

        # Apply format hints based on field name
        for hint_key, fmt in FORMAT_HINTS.items():
            if hint_key in field_lower:
                result["format"] = fmt
                break

    # Apply enums from xlsx "Valid Values" column
    if valid_values and valid_values.strip():
        enum_list = [v.strip() for v in valid_values.split(",") if v.strip()]
        if enum_list:
            if "allOf" in result:
                result["enum"] = enum_list
            else:
                result["enum"] = enum_list

    # Apply default from xlsx "Default Value" column
    if default_value and default_value.strip():
        dv = default_value.strip()
        # Skip expression-like defaults
        if not any(x in dv.lower() for x in ["()", "if ", "then"]):
            if "allOf" in result:
                # For $ref types, add default at top level
                if base_type == "integer" or result.get("type") == "integer":
                    try:
                        result["default"] = int(dv)
                    except ValueError:
                        pass
                elif base_type == "boolean" or result.get("type") == "boolean":
                    result["default"] = dv.lower() in ("true", "1", "yes")
                elif dv == '""':
                    result["default"] = ""
                else:
                    result["default"] = dv
            else:
                if result.get("type") == "integer":
                    try:
                        result["default"] = int(dv)
                    except ValueError:
                        pass
                elif result.get("type") == "boolean":
                    result["default"] = dv.lower() in ("true", "1", "yes")
                elif dv == '""':
                    result["default"] = ""
                else:
                    result["default"] = dv

    # Add x-tier extension
    if required_tier:
        result["x-tier"] = required_tier

    return result


def parse_multiplicity(multiplicity: str) -> tuple[int | None, int | None]:
    """
    Parse multiplicity notation.

    Examples:
        "1" -> (1, 1) - exactly one (required)
        "0..1" -> (0, 1) - optional single
        "1..*" -> (1, None) - one or more
        "0..*" -> (0, None) - zero or more
        "0..n" -> (0, None) - zero or more (n = unbounded)

    Returns (min, max) where None means unbounded.
    """
    if not multiplicity:
        return (0, 1)

    multiplicity = str(multiplicity).strip()

    if ".." in multiplicity:
        parts = multiplicity.split("..")
        min_val = int(parts[0]) if parts[0] not in ("*", "n") else 0
        max_val = None if parts[1] in ("*", "n") else int(parts[1])
        return (min_val, max_val)

    try:
        val = int(multiplicity)
        return (val, val)
    except ValueError:
        return (0, 1)


def to_camel_case(name: str) -> str:
    """Convert to camelCase."""
    parts = name.replace("-", "_").split("_")
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


def build_nested_structure(flat_properties: dict, trigger_required: set) -> tuple[dict, list]:
    """
    Convert flat dotted keys to nested object structure.

    E.g., {"record.sourcesystem": {...}} -> {"record": {"properties": {"sourceSystem": {...}}}}
    """
    nested = {}
    nested_required = set()

    # Group by top-level prefix
    groups: dict[str, list] = {}
    standalone = {}

    for key, prop_def in flat_properties.items():
        if "." in key:
            parts = key.split(".", 1)
            prefix = parts[0]
            suffix = parts[1]
            if prefix not in groups:
                groups[prefix] = []
            groups[prefix].append((suffix, prop_def, key in trigger_required))
        else:
            standalone[key] = prop_def
            if key in trigger_required:
                nested_required.add(key)

    # Build nested objects for groups
    for prefix, fields in groups.items():
        obj_props = {}
        obj_required = []

        for suffix, prop_def, is_trigger in fields:
            prop_key = to_camel_case(suffix)
            obj_props[prop_key] = prop_def

            # Add to required if trigger-required
            if is_trigger:
                obj_required.append(prop_key)

        nested_obj = {
            "type": "object",
            "properties": obj_props,
            "additionalProperties": False,
        }
        if obj_required:
            nested_obj["required"] = obj_required

        nested[prefix] = nested_obj

        # Parent object is required if any of its fields are trigger-required
        if obj_required:
            nested_required.add(prefix)

    # Add standalone properties
    nested.update(standalone)

    return nested, list(nested_required)


def xlsx_to_json_schema(input_path: Path, sheet_name: str = SHEET_NAME) -> dict:
    """Convert Excel data model to JSON Schema."""
    wb = load_workbook(input_path, read_only=True)
    if sheet_name not in wb.sheetnames:
        raise ValueError(f"Sheet '{sheet_name}' not found. Available: {wb.sheetnames}")
    ws = wb[sheet_name]

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel file is empty")

    # First row is headers
    headers = [str(h).strip().lower() if h else "" for h in rows[0]]

    # Find column indices
    col_indices = {}
    for i, header in enumerate(headers):
        if "name" in header:
            col_indices["name"] = i
        elif "description" in header:
            col_indices["description"] = i
        elif "datatype" in header:
            col_indices["datatype"] = i
        elif "multiplicity" in header:
            col_indices["multiplicity"] = i
        elif "required" in header or "tier" in header:
            col_indices["required_tier"] = i
        elif "default" in header:
            col_indices["default_value"] = i
        elif "valid" in header:
            col_indices["valid_values"] = i

    def get_cell(row, key, default=""):
        idx = col_indices.get(key)
        if idx is not None and idx < len(row) and row[idx] is not None:
            return str(row[idx]).strip()
        return default

    # Collect flat properties first
    flat_properties: dict[str, dict] = {}
    trigger_required: set[str] = set()

    # Track array parent definitions for nested properties
    array_parents: dict[str, dict] = {}
    array_parent_meta: dict[str, dict] = {}

    # First pass: identify array parents
    for row in rows[1:]:
        if not row or not any(row):
            continue

        name = get_cell(row, "name")
        if not name:
            continue

        datatype = get_cell(row, "datatype", "string").lower()

        if datatype == "array" and "[]" not in name:
            array_parents[name] = {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            }

    # Second pass: populate properties
    for row in rows[1:]:
        if not row or not any(row):
            continue

        name = get_cell(row, "name")
        if not name:
            continue

        description = get_cell(row, "description")
        datatype = get_cell(row, "datatype", "string")
        multiplicity = get_cell(row, "multiplicity", "1")
        required_tier = get_cell(row, "required_tier").lower()
        default_value = get_cell(row, "default_value")
        valid_values = get_cell(row, "valid_values")

        is_trigger = required_tier == "trigger"
        min_count, max_count = parse_multiplicity(multiplicity)

        # Handle array item properties (e.g., "ServicePoint[].Id")
        if "[]." in name:
            parts = name.split("[].")
            parent_name = parts[0]
            child_name = parts[1]

            if parent_name not in array_parents:
                continue

            prop_key = to_camel_case(child_name)
            full_field_name = f"{parent_name.lower()}.{child_name.lower()}"
            prop_def = map_datatype(datatype, full_field_name, valid_values, default_value, required_tier)

            if description:
                prop_def["description"] = description

            array_parents[parent_name]["properties"][prop_key] = prop_def

            # Add to required if trigger-required
            if is_trigger:
                array_parents[parent_name]["required"].append(prop_key)

        # Store metadata for array parent
        elif name in array_parents:
            array_parent_meta[name] = {
                "description": description,
                "min_count": min_count,
                "max_count": max_count,
                "is_trigger": is_trigger,
                "required_tier": required_tier,
            }

        # Regular property
        else:
            prop_key = name.lower()
            prop_def = map_datatype(datatype, prop_key, valid_values, default_value, required_tier)

            if description:
                prop_def["description"] = description

            # Handle arrays (multiplicity > 1)
            if max_count is None or max_count > 1:
                prop_def = {
                    "type": "array",
                    "items": prop_def,
                    "x-tier": required_tier,
                }
                if description:
                    prop_def["description"] = description
                if min_count > 0:
                    prop_def["minItems"] = min_count
                if max_count is not None:
                    prop_def["maxItems"] = max_count

            flat_properties[prop_key] = prop_def

            # Track trigger-required from xlsx
            if is_trigger:
                trigger_required.add(prop_key)

    # Build nested structure from flat properties
    nested_properties, nested_required = build_nested_structure(flat_properties, trigger_required)

    # Add array parents to nested properties
    for parent_name, items_schema in array_parents.items():
        prop_key = parent_name.lower()
        meta = array_parent_meta.get(parent_name, {})

        # Clean up empty required
        if not items_schema["required"]:
            del items_schema["required"]

        prop_def = {
            "type": "array",
            "items": items_schema,
        }

        if meta.get("description"):
            prop_def["description"] = meta["description"]
        if meta.get("min_count", 0) > 0:
            prop_def["minItems"] = meta["min_count"]
        if meta.get("max_count") is not None:
            prop_def["maxItems"] = meta["max_count"]
        if meta.get("required_tier"):
            prop_def["x-tier"] = meta["required_tier"]

        nested_properties[prop_key] = prop_def

        # Array is required only if marked as trigger in xlsx
        if meta.get("is_trigger"):
            nested_required.append(prop_key)

    # Build final schema
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "Data Model Record",
        "description": "Schema for a single data model record representing customer/account data with contacts, addresses, payment information, and service points.",
        "type": "object",
        "properties": nested_properties,
        "additionalProperties": False,
    }

    if nested_required:
        schema["required"] = sorted(set(nested_required))

    # Add $defs for reusable patterns
    schema["$defs"] = DEFS

    # SEPA conditional logic:
    # Mandate fields required only when method is explicitly SEPA_DIRECT_DEBIT.
    # Defaults in xlsx are informational (runtime hints), not schema enforcement.
    # If method is absent, no additional requirements are imposed by the schema.
    schema["allOf"] = [
        {
            "if": {
                "properties": {
                    "payment": {
                        "properties": {
                            "method": {"const": "SEPA_DIRECT_DEBIT"}
                        },
                        "required": ["method"]
                    }
                }
            },
            "then": {
                "properties": {
                    "payment": {
                        "required": ["mandatereference", "mandatesignaturedate"]
                    }
                }
            }
        }
    ]

    wb.close()
    return schema


def main():
    """Main entry point."""
    print(f"Reading: {INPUT_FILE} (sheet: {SHEET_NAME})")

    if not INPUT_FILE.exists():
        print(f"Error: Input file not found: {INPUT_FILE}")
        return 1

    schema = xlsx_to_json_schema(INPUT_FILE)

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"Generated: {OUTPUT_FILE}")
    print(json.dumps(schema, indent=2))

    return 0


if __name__ == "__main__":
    exit(main())
