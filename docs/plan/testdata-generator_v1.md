# Test Data Generator

## Overview

A test data generation system that:

1. Generates synthetic and semi-realistic test data (Faker + patterns)
2. Stores test data corpus in Excel with multiple sheets by type (Synthetic, UAT)
3. Renders template-based output via Jinja2 templates
4. Supports different profiles (public/internal) for educational publishing without corporate data leakage

## File Structure

```
dat/
├── data-model/incoming/
│   ├── data-model.xlsx              # existing schema definition
│   └── data-model.schema.json       # existing generated schema
├── testdata/
│   ├── corpus.xlsx                  # test case registry
│   │   ├── Sheet: Synthetic         # generated test cases
│   │   └── Sheet: UAT               # real UAT test cases (manual)
│   ├── profiles.yaml                # rendering profiles config
│   ├── templates/                   # Jinja2 templates
│   │   ├── public.j2
│   │   ├── internal.j2
│   │   └── json.j2
│   ├── mappings/                    # field name mappings
│   │   └── public.yaml
│   └── generated/                   # output folder (per profile)
│       ├── public/
│       ├── internal/
│       └── validation/
└── systems.yaml

tools/
├── xlsx_to_json_schema.py           # existing
├── generate_testdata.py             # generates test cases
└── render_testdata.py               # renders via Jinja2 templates
```

## Dependencies

Dependencies are defined in `pyproject.toml` under `[project.optional-dependencies]` > `plan`:

```bash
uv pip install -e ".[plan]"
```

## Tools

### `tools/generate_testdata.py`

Generates synthetic test data into the corpus Excel file.

**Parameters:**
- `--count N`: number of records to generate (configurable)
- `--append`: append to existing corpus or overwrite

**Data Generation:**
- Uses Faker (de_DE locale) for realistic data: names, addresses, companies, IBANs, BICs
- Uses pattern-based generation for technical fields: account numbers, mandate references, identifiers

**Generated Test Cases:**
- Valid happy-path (1-10 ServicePoints)
- Invalid cases (0 ServicePoints, missing fields, bad IBANs, etc.)
- Boundary cases (11 ServicePoints, max-length strings, etc.)

Each row includes `ExpectedResult` (PASS/FAIL/specific error).

### `tools/render_testdata.py`

Renders corpus data to text files using Jinja2 templates.

**Parameters:**
- `--profile`: profile name (loads from profiles.yaml)
- `--rows`: row index/range (e.g., "1", "1-5", "all") - overrides profile count

## Configuration

### Profiles (`dat/testdata/profiles.yaml`)

Profiles control rendering behavior:

```yaml
profiles:
  public:
    description: "Public educational samples"
    count: 10
    output_dir: "dat/testdata/generated/public"
    template: "templates/public.j2"
    field_mapping: "mappings/public.yaml"

  internal:
    description: "Internal documentation samples"
    count: 5
    output_dir: "dat/testdata/generated/internal"
    template: "templates/internal.j2"
    field_mapping: null  # use original field names

  validation:
    description: "Full corpus for validation testing"
    count: all
    output_dir: "dat/testdata/generated/validation"
    template: "templates/json.j2"
    field_mapping: null
```

### Jinja2 Templates (`dat/testdata/templates/`)

**public.j2** (Key: Value with mapped names):
```jinja2
{# Public template with neutral field names #}
{% for key, value in record.items() %}
{{ field_map.get(key, key) }}: {{ value }}
{% endfor %}
```

**internal.j2** (Key: Value with original names):
```jinja2
{# Internal template with original field names #}
{% for key, value in record.items() %}
{{ key }}: {{ value }}
{% endfor %}
```

**json.j2** (JSON output):
```jinja2
{{ record | tojson(indent=2) }}
```

### Field Mappings (`dat/testdata/mappings/`)

**public.yaml** - Maps internal field names to neutral public names:
```yaml
Account.Number: CustomerRef
Contact.Email: EmailAddress
Contact.FullName: FullName
Contact.Phone: PhoneNumber
Payment.IBAN: BankAccount
Payment.BIC: BankCode
# ... etc
```

## Corpus Excel Structure

### Test Case Registry Columns

| Column | Description |
|--------|-------------|
| TestCaseId | Unique identifier (TC001, TC002...) |
| TestType | valid, invalid, boundary |
| Description | Human-readable test case description |
| ExpectedResult | PASS, FAIL, ERROR, or specific validation message |
| ExecutionLog | Optional: log output from test run |

### Trigger Data Columns (flattened)

| Column | Description |
|--------|-------------|
| Record.SourceSystem | Upstream system code |
| Account.Number | Account/customer reference |
| Contact.Email | Email address |
| Contact.FullName | Display name |
| Contact.Phone | Phone number |
| ... | (all trigger fields from data model) |

### ServicePoints Column (pipe-delimited format)

| Column | Example |
|--------|---------|
| ServicePoints | `POSTBOX|12345|Berlin;ADDRESS|54321|Munich` |

**Format:** `Type|PostalCode|City` per ServicePoint, separated by `;`

- Empty string = 0 ServicePoints (invalid case)
- Single entry = 1 ServicePoint
- Multiple entries separated by `;` = 2+ ServicePoints

## Usage Examples

```bash
# Generate 20 synthetic test cases
python tools/generate_testdata.py --count 20

# Render using public profile
python tools/render_testdata.py --profile public

# Render specific rows with internal profile
python tools/render_testdata.py --profile internal --rows 1-5

# Render all rows as JSON for validation
python tools/render_testdata.py --profile validation --rows all
```
