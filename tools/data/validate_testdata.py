#!/usr/bin/env python3
"""
Validate test data against JSON Schema.

Chainable tool that reads JSON from stdin and outputs validation results to stdout.
Can also read from files and validate directories.

Features:
- Reads JSON from stdin (or --input file/directory)
- Validates against JSON Schema
- Outputs validation results as JSON to stdout
- Exit code: 0=all pass, 1=any fail
"""

import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from jsonschema import Draft7Validator, ValidationError

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SCHEMA_DIR = PROJECT_ROOT / "dat" / "data-model" / "generated"

app = typer.Typer(help="Validate test data against JSON Schema.")


def load_schema(schema_path: Path) -> dict:
    """Load JSON Schema from file."""
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_data_from_stdin() -> list[dict]:
    """Load data from JSON on stdin."""
    if sys.stdin.isatty():
        raise ValueError("No input on stdin. Use --input for file input or pipe JSON.")

    data = json.load(sys.stdin)

    # Normalize to list
    if isinstance(data, dict):
        data = [data]

    return data


def load_data_from_file(file_path: Path) -> list[dict]:
    """Load data from JSON file."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Normalize to list
    if isinstance(data, dict):
        data = [data]

    return data


def load_data_from_directory(dir_path: Path) -> list[dict]:
    """Load all JSON files from a directory."""
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    data = []
    for json_file in sorted(dir_path.glob("*.json")):
        with open(json_file, "r", encoding="utf-8") as f:
            item = json.load(f)
            item["_source_file"] = str(json_file.name)
            data.append(item)

    return data


def validate_item(item: dict, validator: Draft7Validator, item_id: str) -> dict:
    """Validate a single item against the schema."""
    errors = list(validator.iter_errors(item))

    if errors:
        return {
            "id": item_id,
            "valid": False,
            "errors": [
                {
                    "path": ".".join(str(p) for p in error.absolute_path),
                    "message": error.message,
                    "validator": error.validator,
                }
                for error in errors
            ],
        }
    else:
        return {
            "id": item_id,
            "valid": True,
            "errors": [],
        }


def extract_record_for_validation(item: dict) -> tuple[dict, str]:
    """Extract the record to validate and its ID from various input formats."""
    # Format 1: render_testdata.py output {testCaseId, rendered, metadata}
    if "testCaseId" in item and "rendered" in item:
        # Try to parse rendered content as JSON
        try:
            record = json.loads(item["rendered"])
            return record, item["testCaseId"]
        except json.JSONDecodeError:
            # Rendered content is not JSON (e.g., text template)
            return item, item["testCaseId"]

    # Format 2: generate_testdata.py output {metadata, record, servicePoints}
    if "metadata" in item and "record" in item:
        test_id = item["metadata"].get("TestCaseId", "unknown")
        # Combine record and servicePoints for validation
        record = dict(item["record"])
        if "servicePoints" in item:
            record["servicePoints"] = item["servicePoints"]
        return record, test_id

    # Format 3: Direct record with _source_file (from directory)
    if "_source_file" in item:
        source = item.pop("_source_file")
        return item, source

    # Format 4: Direct record
    return item, item.get("TestCaseId", item.get("testCaseId", "unknown"))


@app.command()
def main(
    input_path: Annotated[Optional[Path], typer.Option("--input", "-i", help="Input file or directory. Omit to read JSON from stdin.")] = None,
    schema: Annotated[Optional[Path], typer.Option("--schema", "-s", help="JSON Schema file path")] = None,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress status messages (for piping)")] = False,
    summary_only: Annotated[bool, typer.Option("--summary", help="Only output summary, not individual results")] = False,
):
    """Validate test data against JSON Schema.

    By default, reads JSON from stdin and writes validation results to stdout.
    Use --input for file or directory input.

    Exit code: 0 if all valid, 1 if any invalid.
    """
    def log(msg: str):
        if not quiet:
            print(msg, file=sys.stderr)

    # Load schema
    if schema:
        schema_path = schema if schema.is_absolute() else PROJECT_ROOT / schema
    else:
        # Default schema location
        schema_path = SCHEMA_DIR / "schema.json"

    log(f"Loading schema from: {schema_path}")
    try:
        json_schema = load_schema(schema_path)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    validator = Draft7Validator(json_schema)

    # Load data
    if input_path is None:
        log("Reading JSON from stdin...")
        try:
            data = load_data_from_stdin()
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)
    elif input_path.is_dir():
        log(f"Loading JSON files from directory: {input_path}")
        data = load_data_from_directory(input_path)
    else:
        log(f"Loading from file: {input_path}")
        data = load_data_from_file(input_path)

    log(f"  Found {len(data)} items to validate")

    if not data:
        typer.echo("No data to validate.", err=True)
        raise typer.Exit(1)

    # Validate each item
    results = []
    valid_count = 0
    invalid_count = 0

    for item in data:
        record, item_id = extract_record_for_validation(item)
        result = validate_item(record, validator, item_id)
        results.append(result)

        if result["valid"]:
            valid_count += 1
        else:
            invalid_count += 1

    # Summary
    summary = {
        "total": len(results),
        "valid": valid_count,
        "invalid": invalid_count,
        "pass_rate": f"{(valid_count / len(results) * 100):.1f}%" if results else "N/A",
    }

    log(f"\nValidation Summary:")
    log(f"  Total: {summary['total']}")
    log(f"  Valid: {summary['valid']}")
    log(f"  Invalid: {summary['invalid']}")
    log(f"  Pass rate: {summary['pass_rate']}")

    # Output results
    if summary_only:
        output = summary
    else:
        output = {
            "summary": summary,
            "results": results,
        }

    print(json.dumps(output, indent=2, ensure_ascii=False))

    # Exit code based on validation
    if invalid_count > 0:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
