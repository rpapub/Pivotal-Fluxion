---
date: 2025-12-05
authors:
  - Christian Prior-Mamulyan
categories:
  - Testing
  - Functional Programming
  - Architecture
tags:
  - test-data
  - pipelines
  - unix-philosophy
  - jinja2
  - python
---

# Chainable Test Data Pipelines: From Procedural Scripts to Functional Composition

When building test data generators, the temptation exists to create a monolithic script that does everything: generate data, format it, validate it, and write it to files. This approach works initially, but quickly becomes a maintenance burden when requirements change. And in testing, requirements *always* change.

This post explores how test data tooling can evolve from a procedural, file-centric approach to a composable, stream-based pipeline that embraces functional programming principles.

<!-- more -->

## The Problem with Procedural Test Data Scripts

A typical initial test data generator looks like many others: a single Python script that generates synthetic records and writes them directly to an Excel file. The rendering tool then reads from that Excel file and produces output files.

```
generate_testdata.py → corpus.xlsx → render_testdata.py → files
```

This works, but has several problems:

1. **Tight Coupling**: The generator *knows* it writes Excel. The renderer *knows* it reads Excel. Change the intermediate format, and both tools break.

2. **No Composability**: Want to validate before rendering? Add another tool that reads Excel. Want to filter records? Modify the generator. Every change requires modifying existing code.

3. **Hidden State**: The Excel file becomes implicit shared state. Which sheet? What format? These turn into hardcoded assumptions scattered across tools.

4. **Testing Difficulty**: To test the renderer, an Excel file must first be generated. Integration tests become the only option.

## The Unix Philosophy: Do One Thing Well

The Unix philosophy offers a better model:

> Write programs that do one thing and do it well. Write programs to work together. Write programs to handle text streams, because that is a universal interface.

Applied to test data tooling, this means:

- **Generate** data (without formatting it)
- **Render** templates (without caring where data comes from)
- **Validate** records (without caring what happens next)

Each tool should be a pure transformation: input to output.

## Stream-Centric Design

The refactored pipeline uses JSON as the universal interchange format, with stdin/stdout as the default I/O:

```bash
generate_testdata.py --count 20 | render_testdata.py render --template form.j2 | validate_testdata.py
```

Each tool:

- Reads JSON from **stdin** (or `--input file` for backwards compatibility)
- Writes JSON to **stdout** (or `--output file/dir` as a sink)
- Uses **stderr** for status messages (controlled by `--quiet`)

The Excel format becomes just another output option, not the central hub:

```bash
# Still works when Excel output is needed
generate_testdata.py --count 50 --output corpus.xlsx
```

## Flexibility When Requirements Change

This design shines when requirements change.

### Scenario: New Template Format

**Before**: Modify the renderer to handle the new format, test the entire pipeline.

**After**: Create a new template file, pipe through the same renderer:

```bash
generate_testdata.py --count 10 | render_testdata.py render --template new-format.j2
```

### Scenario: Add Validation

**Before**: Add validation logic to either the generator or renderer, or create a new tool that reads Excel.

**After**: Pipe through the validator:

```bash
generate_testdata.py --count 20 | validate_testdata.py --schema schema.json
```

### Scenario: Filter Test Cases

**Before**: Add filtering logic to the generator.

**After**: Use standard Unix tools:

```bash
generate_testdata.py --count 100 | jq '[.[] | select(.metadata.TestType == "boundary")]'
```

### Scenario: Different Output Formats

**Before**: Add format options to each tool.

**After**: Transform at the end of the pipeline:

```bash
generate_testdata.py --count 5 | render_testdata.py render --template form.j2 | jq -r '.[].rendered'
```

## The Functional Programming Connection

This stream-based approach directly reflects functional programming principles:

### Pure Functions

Each tool is conceptually a pure function: `Input → Output`. No hidden state, no side effects (except the final sink). Given the same input, the same output results.

```python
# Conceptually:
def generate(count: int) -> list[TestCase]: ...
def render(cases: list[TestCase], template: Template) -> list[RenderedOutput]: ...
def validate(data: list[dict], schema: Schema) -> ValidationResult: ...
```

### Function Composition

The Unix pipe (`|`) is function composition:

```bash
generate | render | validate
# Is equivalent to:
# validate(render(generate()))
```

### Immutable Data Flow

Data flows through the pipeline without mutation. Each tool receives input, produces output, and never modifies the original. This makes debugging trivial. Any point in the pipeline can be inspected:

```bash
# Debug: what does generate produce?
generate_testdata.py --count 3 | jq .

# Debug: what does render produce?
generate_testdata.py --count 1 | render_testdata.py render --template form.j2 | jq .
```

### Lazy Evaluation (Conceptual)

While the current implementation loads full arrays, the stream model supports lazy evaluation. A future enhancement could use JSON Lines (JSONL) for true streaming:

```bash
generate_testdata.py --count 1000000 --format jsonl | head -100 | render_testdata.py ...
```

## Implementation Highlights

### Quiet Mode for Piping

Status messages go to stderr, controlled by `--quiet`:

```python
def log(msg: str):
    if not quiet:
        print(msg, file=sys.stderr)
```

This allows clean piping while still showing progress when running interactively.

### Flexible Input Sources

The renderer accepts multiple input formats:

```python
def load_corpus(input_path: Optional[Path], sheet_name: str) -> list[dict]:
    if input_path is None:
        return load_corpus_from_stdin()
    if str(input_path).endswith(".xlsx"):
        return load_corpus_from_xlsx(input_path, sheet_name)
    else:
        return load_corpus_from_json(input_path)
```

### Normalized Internal Format

All tools agree on a common JSON structure:

```json
{
  "metadata": {
    "TestCaseId": "TC001",
    "TestType": "valid",
    "Description": "...",
    "ExpectedResult": "PASS"
  },
  "record": {
    "Account.Number": "ACC-123456",
    "Contact.Email": "test@example.com"
  },
  "servicePoints": [
    {"type": "POSTBOX", "postalcode": "12345", "city": "Berlin"}
  ]
}
```

This separation of metadata (test harness concerns) from record (domain data) keeps responsibilities clear.

## From Procedural to Functional: The Journey

The evolution from procedural to functional is not about rewriting everything in Haskell. It is about adopting functional *thinking*:

1. **Separate data from behavior**: Test cases are data. Rendering is a transformation. Validation is a predicate.

2. **Compose small pieces**: A 500-line script becomes three 150-line tools that can be combined in ways the original author never imagined.

3. **Embrace immutability**: Data flows forward. No tool modifies another tool's output in place.

4. **Make dependencies explicit**: stdin/stdout makes data flow visible. No hidden file dependencies.

5. **Design for testability**: Each tool can be tested in isolation with crafted JSON input.

## Conclusion

The chainable test data pipeline demonstrates that functional programming principles apply far beyond "pure" functional languages. By treating tools as composable transformations over immutable data streams, the following benefits emerge:

- **Flexibility**: New requirements do not require modifying existing tools
- **Debuggability**: Any point in the pipeline can be inspected
- **Testability**: Each tool can be unit tested in isolation
- **Reusability**: Tools combine in unanticipated ways

The Unix philosophy and functional programming converge on the same insight: small, focused, composable pieces beat monolithic solutions every time.

*This post is part of the Pivotal Fluxion series, exploring the journey from procedural to functional programming through practical examples.*
