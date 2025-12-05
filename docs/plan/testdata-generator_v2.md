# Chainable Test Data Pipeline (v2)

## Status: IMPLEMENTED

## Goal
Unix-style chainable tools: stdin → stdout, with file output as optional sinks.

## Design
```bash
generate_testdata.py --count 20 | render_testdata.py render --template foo.j2 | validate_testdata.py
```

Each tool:
- Reads JSON from **stdin** (or `--input file`)
- Writes JSON to **stdout** (or `--output file/dir`)
- xlsx becomes just another output format, not the hub

## Usage Examples

### Streaming Pipeline
```bash
# Generate → Render → Validate
generate_testdata.py --count 20 --quiet | \
  render_testdata.py render --template templates/2025-12.j2 --quiet | \
  validate_testdata.py --schema schema.json --quiet

# Generate and render to files
generate_testdata.py --count 10 --quiet | \
  render_testdata.py render --template templates/2025-12.j2 --output dat/testdata/generated/output/
```

### File-Based (Backwards Compatible)
```bash
# Generate to xlsx
generate_testdata.py --count 50 --output dat/testdata/corpus.xlsx

# Render from xlsx to files
render_testdata.py render --input dat/testdata/corpus.xlsx --template templates/2025-12.j2 --output dat/testdata/generated/2025-12/

# Validate directory of JSON files
validate_testdata.py --input dat/testdata/generated/validation/ --schema schema.json
```

### Using Profiles
```bash
# Render with profile (reads from profile's configured input)
render_testdata.py render --profile validation --output dat/testdata/generated/validation/
```

## Tool Reference

### generate_testdata.py
```
Options:
  --count, -n     Number of test cases (default: 20)
  --output, -o    Output file (.xlsx or .json). Omit for stdout JSON.
  --append, -a    Append to existing xlsx corpus
  --dry-run       Preview without writing
  --quiet, -q     Suppress stderr messages (for piping)
```

### render_testdata.py render
```
Options:
  --profile, -p       Profile name (from dat/testdata/profiles/)
  --template, -t      Template path (overrides profile)
  --input, -i         Input file (.xlsx, .json). Omit for stdin.
  --output, -o        Output directory. Omit for stdout JSON.
  --rows, -r          Row range (e.g., '1', '1-5', 'all')
  --sheet, -s         Sheet name for xlsx input (default: Synthetic)
  --dry-run           Preview without writing
  --quiet, -q         Suppress stderr messages (for piping)
```

### validate_testdata.py
```
Options:
  --input, -i     Input file or directory. Omit for stdin.
  --schema, -s    JSON Schema file path
  --summary       Only output summary, not individual results
  --quiet, -q     Suppress stderr messages (for piping)

Exit codes: 0=all valid, 1=any invalid
```

## Internal JSON Format

### generate_testdata.py output / render_testdata.py input:
```json
[
  {
    "metadata": {
      "TestCaseId": "TC001",
      "TestType": "valid",
      "Description": "...",
      "ExpectedResult": "PASS"
    },
    "record": {
      "Account.Number": "...",
      ...
    },
    "servicePoints": [
      {"type": "POSTBOX", "postalcode": "12345", "city": "Berlin", ...}
    ]
  }
]
```

### render_testdata.py output:
```json
[
  {
    "testCaseId": "TC001",
    "rendered": "... rendered template content ...",
    "metadata": {...}
  }
]
```

## Files
- `tools/generate_testdata.py` - Generate synthetic test data
- `tools/render_testdata.py` - Render with Jinja2 templates
- `tools/validate_testdata.py` - Validate against JSON Schema
