# Data Tools

Command-line tools for test data generation, rendering, and validation. Designed as chainable Unix-style pipelines.

## Tools Overview

| Tool | Purpose |
|------|---------|
| `generate_testdata.py` | Generate synthetic test data |
| `render_testdata.py` | Render data using Jinja2 templates |
| `validate_testdata.py` | Validate data against JSON Schema |
| `xlsx_to_json_schema.py` | Convert data model Excel to JSON Schema |

## Installation

```bash
just sync
# or
uv sync --no-install-project --extra plan
```

## Pipeline Usage

Tools read JSON from stdin and write to stdout by default, enabling Unix-style piping:

```bash
# Generate, render, and validate in one pipeline
python tools/data/generate_testdata.py --count 20 --quiet | \
  python tools/data/render_testdata.py render --template templates/2025-12.j2 --quiet | \
  python tools/data/validate_testdata.py --schema schema.json --quiet

# Generate and write to files
python tools/data/generate_testdata.py --count 10 --quiet | \
  python tools/data/render_testdata.py render --template templates/2025-12.j2 --output dat/testdata/generated/output/
```

## generate_testdata.py

Generate synthetic test data using Faker (de_DE locale).

```
Usage: generate_testdata.py [OPTIONS]

Options:
  -n, --count INTEGER   Number of test cases to generate [default: 20]
  -o, --output PATH     Output file (.xlsx or .json). Omit for stdout.
  -a, --append          Append to existing xlsx corpus
  --dry-run             Show what would be generated without writing
  -q, --quiet           Suppress status messages (for piping)
  --help                Show this message and exit.
```

### Examples

```bash
# Output JSON to stdout
python tools/data/generate_testdata.py --count 10

# Write to Excel corpus
python tools/data/generate_testdata.py --count 64 --output dat/testdata/corpus.xlsx

# Append to existing corpus
python tools/data/generate_testdata.py --count 10 --append --output dat/testdata/corpus.xlsx

# Preview without writing
python tools/data/generate_testdata.py --count 50 --dry-run
```

### Output Format

Outputs a JSON array of test cases:

```json
[
  {
    "metadata": {
      "TestCaseId": "TC001",
      "TestType": "valid",
      "Description": "Valid case with 5 service point(s)",
      "ExpectedResult": "PASS",
      "ExecutionLog": ""
    },
    "record": {
      "Account.Number": "ACC-123456",
      "Contact.Email": "user@example.com",
      ...
    },
    "servicePoints": [
      {"type": "POSTBOX", "postalcode": "12345", "city": "Berlin", ...}
    ]
  }
]
```

### Test Case Distribution

- ~60% valid (happy path)
- ~25% invalid (missing fields, bad formats)
- ~15% boundary (edge cases)

## render_testdata.py

Render test data using Jinja2 templates.

```
Usage: render_testdata.py [OPTIONS] COMMAND [ARGS]...

Commands:
  list    List available profiles.
  render  Render test data using Jinja2 templates.
```

### render subcommand

```
Usage: render_testdata.py render [OPTIONS]

Options:
  -p, --profile TEXT       Profile name (from dat/testdata/profiles/)
  -t, --template PATH      Template path (overrides profile)
  -r, --rows TEXT          Row range (e.g., '1', '1-5', 'all')
  -s, --sheet TEXT         Sheet name for xlsx input [default: Synthetic]
  -i, --input PATH         Input file (.xlsx, .json). Omit for stdin.
  -o, --output PATH        Output directory. Omit for stdout.
  -d, --profiles-dir PATH  Profiles directory
  --dry-run                Show what would be rendered without writing
  -q, --quiet              Suppress status messages (for piping)
  --help                   Show this message and exit.
```

### list subcommand

```
Usage: render_testdata.py list [OPTIONS]

Options:
  -d, --profiles-dir PATH  Profiles directory
  --help                   Show this message and exit.
```

### Examples

```bash
# Render from stdin to stdout
python tools/data/generate_testdata.py --count 5 --quiet | \
  python tools/data/render_testdata.py render --template templates/2025-12.j2

# Render from xlsx to directory
python tools/data/render_testdata.py render \
  --input dat/testdata/corpus.xlsx \
  --template templates/2025-12.j2 \
  --output dat/testdata/generated/2025-12/

# Use a profile
python tools/data/render_testdata.py render --profile validation

# Render specific rows
python tools/data/render_testdata.py render \
  --input dat/testdata/corpus.xlsx \
  --template templates/2025-12.j2 \
  --rows 1-10

# List available profiles
python tools/data/render_testdata.py list
```

### Output Format (stdout mode)

```json
[
  {
    "testCaseId": "TC001",
    "rendered": "... rendered template content ...",
    "metadata": {
      "TestCaseId": "TC001",
      "TestType": "valid",
      ...
    }
  }
]
```

## validate_testdata.py

Validate data against JSON Schema.

```
Usage: validate_testdata.py [OPTIONS]

Options:
  -i, --input PATH    Input file or directory. Omit for stdin.
  -s, --schema PATH   JSON Schema file path
  -q, --quiet         Suppress status messages (for piping)
  --summary           Only output summary, not individual results
  --help              Show this message and exit.

Exit codes:
  0  All records valid
  1  One or more records invalid
```

### Examples

```bash
# Validate from stdin
python tools/data/generate_testdata.py --count 10 --quiet | \
  python tools/data/validate_testdata.py --schema dat/data-model/incoming/data-model.schema.json

# Validate a directory of JSON files
python tools/data/validate_testdata.py \
  --input dat/testdata/generated/validation/ \
  --schema dat/data-model/incoming/data-model.schema.json

# Summary only
python tools/data/validate_testdata.py --input data.json --schema schema.json --summary
```

### Output Format

```json
{
  "summary": {
    "total": 20,
    "valid": 18,
    "invalid": 2,
    "pass_rate": "90.0%"
  },
  "results": [
    {
      "id": "TC001",
      "valid": true,
      "errors": []
    },
    {
      "id": "TC002",
      "valid": false,
      "errors": [
        {
          "path": "contact.email",
          "message": "'not-an-email' is not a 'email'",
          "validator": "format"
        }
      ]
    }
  ]
}
```

## xlsx_to_json_schema.py

Convert the data model Excel file to JSON Schema.

```bash
python tools/data/xlsx_to_json_schema.py
```

This tool has no CLI options. It reads from `dat/data-model/incoming/data-model.xlsx` and writes to `dat/data-model/incoming/data-model.schema.json`.

### Features

- Nested structures from dot notation (`Record.SourceSystem` becomes `record.sourceSystem`)
- Array support with bracket notation (`ServicePoint[].Id`)
- Format constraints (date, email, date-time)
- Pattern definitions for IBAN, BIC, phone numbers, postal codes
- Enum values from "Valid Values" column
- Default values from "Default Value" column
- Required field detection based on tier (trigger fields are required)
- SEPA conditional validation (mandate required when method is SEPA_DIRECT_DEBIT)

## Profiles

Profiles are YAML files in `dat/testdata/profiles/` that configure rendering:

```yaml
# dat/testdata/profiles/validation.yaml
description: "Render as JSON for schema validation"
template: "templates/json.j2"
output_dir: "dat/testdata/generated/validation"
count: all
```

Available profiles:
- `public` - Public-facing field names
- `internal` - Internal field names
- `validation` - JSON output for schema validation
- `example` - Example template showing all fields

## Templates

Templates are Jinja2 files in `dat/testdata/templates/`. Available variables:

- `record` - Field values (e.g., `record['Account.Number']`)
- `metadata` - Test case metadata (TestCaseId, TestType, Description, ExpectedResult)
- `service_points` - List of service point dictionaries
- `field_map` - Field name mapping (if configured in profile)
