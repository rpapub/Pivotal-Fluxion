#!/usr/bin/env python3
"""
Generate synthetic test data based on the data model.

Chainable tool that outputs JSON to stdout by default.
Can also write to xlsx or JSON files.

Features:
- Uses Faker (de_DE locale) for realistic German data
- Pattern-based generation for technical fields
- Generates valid, invalid, and boundary test cases
- Outputs JSON to stdout for piping to other tools
"""

import json
import random
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from faker import Faker
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

# Initialize Faker with German locale
fake = Faker("de_DE")
Faker.seed(42)
random.seed(42)

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_MODEL_FILE = PROJECT_ROOT / "dat" / "data-model" / "incoming" / "data-model.xlsx"
CORPUS_FILE = PROJECT_ROOT / "dat" / "testdata" / "corpus.xlsx"

# Service point types
SERVICE_POINT_TYPES = ["POSTBOX", "ADDRESS", "PICKUP_POINT", "LOCKER"]

# Payment schedules
PAYMENT_SCHEDULES = ["TEN_DAYS", "MONTHLY", "QUARTERLY", "SEMI_ANNUALLY", "ANNUALLY"]

# Payment methods
PAYMENT_METHODS = ["SEPA_DIRECT_DEBIT", "BANK_TRANSFER", "CREDIT_CARD", "INVOICE"]

# Preferred channels
PREFERRED_CHANNELS = ["PHONE", "EMAIL", "MAIL"]

# Payer types
PAYER_TYPES = ["PERSON", "ORGANIZATION"]

# Legal forms
LEGAL_FORMS = ["GmbH", "AG", "KG", "OHG", "e.K.", "UG", "GbR"]

# Metadata columns (not part of record data)
METADATA_KEYS = ["TestCaseId", "TestType", "Description", "ExpectedResult", "ExecutionLog"]

app = typer.Typer(help="Generate synthetic test data for the data model.")


def generate_account_number() -> str:
    """Generate a realistic account number."""
    return f"ACC-{random.randint(100000, 999999)}"


def generate_mandate_reference() -> str:
    """Generate a SEPA mandate reference."""
    return f"MNDT-{fake.uuid4()[:8].upper()}-{random.randint(1000, 9999)}"


def generate_service_point() -> dict:
    """Generate a single service point."""
    return {
        "type": random.choice(SERVICE_POINT_TYPES),
        "postalcode": fake.postcode(),
        "city": fake.city(),
        "identifier": f"SP-{random.randint(10000, 99999)}",
        "enabled": True,
    }


def service_points_to_pipe_format(service_points: list[dict]) -> str:
    """
    Convert service points to pipe-delimited format.

    Format: Type|PostalCode|City per ServicePoint, separated by ;
    """
    if not service_points:
        return ""

    parts = []
    for sp in service_points:
        parts.append(f"{sp['type']}|{sp['postalcode']}|{sp['city']}")

    return ";".join(parts)


def generate_valid_iban() -> str:
    """Generate a valid German IBAN."""
    return fake.iban()


def generate_invalid_iban() -> str:
    """Generate an invalid IBAN."""
    choices = [
        "DE00000000000000000000",  # Invalid checksum
        "XX89370400440532013000",  # Invalid country code
        "DE89",  # Too short
        "NOTANIBAN",  # Not an IBAN at all
    ]
    return random.choice(choices)


def generate_valid_bic() -> str:
    """Generate a valid BIC."""
    return fake.bban()[:8] + "XXX" if random.random() > 0.5 else fake.swift()


def generate_booking_text() -> str:
    """Generate a booking reference text."""
    return f"Rechnung {random.randint(2024001, 2024999)}"


def generate_valid_test_case(test_id: int) -> dict:
    """Generate a valid happy-path test case."""
    num_service_points = random.randint(1, 10)
    service_points = [generate_service_point() for _ in range(num_service_points)]

    payer_type = random.choice(PAYER_TYPES)
    dob = fake.date_of_birth(minimum_age=18, maximum_age=80)

    return {
        "TestCaseId": f"TC{test_id:03d}",
        "TestType": "valid",
        "Description": f"Valid case with {num_service_points} service point(s)",
        "ExpectedResult": "PASS",
        "ExecutionLog": "",
        # Record fields (generated/defaulted - not in trigger)
        "Record.SourceSystem": "RPA-Process",
        # Account fields
        "Account.Number": generate_account_number(),
        # Contact fields
        "Contact.Email": fake.email(),
        "Contact.FullName": fake.name(),
        "Contact.Phone": fake.phone_number(),
        "Contact.CallbackWindow": f"{random.randint(9, 12)}:00-{random.randint(14, 18)}:00",
        "Contact.PreferredChannel": random.choice(PREFERRED_CHANNELS),
        "Contact.Timezone": "Europe/Berlin",
        # Organization fields
        "Organization.Name": fake.company(),
        "Organization.LegalForm": random.choice(LEGAL_FORMS),
        "Organization.OwnerName": fake.name(),
        # Address fields
        "Address.AddressLine1": fake.street_address(),
        "Address.AddressLine2": "" if random.random() > 0.3 else f"c/o {fake.name()}",
        "Address.HouseNumber": str(random.randint(1, 200)),
        "Address.Additional": "" if random.random() > 0.2 else f"Etage {random.randint(1, 10)}",
        "Address.PostalCode": fake.postcode(),
        "Address.City": fake.city(),
        "Address.Region": random.choice(["Bayern", "Hessen", "NRW", "Baden-Württemberg", ""]),
        "Address.Country": "Deutschland",
        # Payment fields
        "Payment.IBAN": generate_valid_iban(),
        "Payment.BIC": fake.swift(),
        "Payment.BookingText": generate_booking_text(),
        "Payment.Schedule": random.choice(PAYMENT_SCHEDULES),
        "Payment.Currency": "EUR",
        "Payment.Method": "SEPA_DIRECT_DEBIT",
        "Payment.MandateReference": generate_mandate_reference(),
        "Payment.MandateSignatureDate": fake.date_between(start_date="-2y", end_date="today").isoformat(),
        # Payer fields
        "Payer.Type": payer_type,
        "Payer.FirstName": fake.first_name(),
        "Payer.LastName": fake.last_name(),
        "Payer.DateOfBirth": dob.isoformat(),
        # Service points (pipe-delimited for xlsx, will be parsed for JSON)
        "ServicePoints": service_points_to_pipe_format(service_points),
        # Keep raw service points for JSON output
        "_servicePoints": service_points,
    }


def generate_invalid_test_case(test_id: int, invalid_type: str) -> dict:
    """Generate an invalid test case."""
    base = generate_valid_test_case(test_id)
    base["TestType"] = "invalid"

    if invalid_type == "zero_service_points":
        base["ServicePoints"] = ""
        base["_servicePoints"] = []
        base["Description"] = "Invalid: 0 service points"
        base["ExpectedResult"] = "FAIL: ServicePoints array requires at least 1 item"

    elif invalid_type == "invalid_iban":
        base["Payment.IBAN"] = generate_invalid_iban()
        base["Description"] = "Invalid: malformed IBAN"
        base["ExpectedResult"] = "FAIL: Invalid IBAN format"

    elif invalid_type == "missing_email":
        base["Contact.Email"] = ""
        base["Description"] = "Invalid: missing required email"
        base["ExpectedResult"] = "FAIL: Contact.Email is required"

    elif invalid_type == "missing_account_number":
        base["Account.Number"] = ""
        base["Description"] = "Invalid: missing account number"
        base["ExpectedResult"] = "FAIL: Account.Number is required"

    elif invalid_type == "missing_mandate_for_sepa":
        base["Payment.Method"] = "SEPA_DIRECT_DEBIT"
        base["Payment.MandateReference"] = ""
        base["Description"] = "Invalid: SEPA without mandate reference"
        base["ExpectedResult"] = "FAIL: MandateReference required for SEPA_DIRECT_DEBIT"

    elif invalid_type == "invalid_email_format":
        base["Contact.Email"] = "not-an-email"
        base["Description"] = "Invalid: malformed email address"
        base["ExpectedResult"] = "FAIL: Invalid email format"

    elif invalid_type == "missing_fullname":
        base["Contact.FullName"] = ""
        base["Description"] = "Invalid: missing contact full name"
        base["ExpectedResult"] = "FAIL: Contact.FullName is required"

    elif invalid_type == "missing_organization_name":
        base["Organization.Name"] = ""
        base["Description"] = "Invalid: missing organization name"
        base["ExpectedResult"] = "FAIL: Organization.Name is required"

    return base


def generate_boundary_test_case(test_id: int, boundary_type: str) -> dict:
    """Generate a boundary test case."""
    base = generate_valid_test_case(test_id)
    base["TestType"] = "boundary"

    if boundary_type == "eleven_service_points":
        service_points = [generate_service_point() for _ in range(11)]
        base["ServicePoints"] = service_points_to_pipe_format(service_points)
        base["_servicePoints"] = service_points
        base["Description"] = "Boundary: 11 service points (above typical maximum)"
        base["ExpectedResult"] = "PASS"  # Schema allows it, just unusual

    elif boundary_type == "max_length_strings":
        base["Contact.FullName"] = fake.name() + " " * 50 + fake.name()
        base["Address.AddressLine1"] = "A" * 200
        base["Description"] = "Boundary: maximum length strings"
        base["ExpectedResult"] = "PASS"

    elif boundary_type == "single_service_point":
        service_points = [generate_service_point()]
        base["ServicePoints"] = service_points_to_pipe_format(service_points)
        base["_servicePoints"] = service_points
        base["Description"] = "Boundary: exactly 1 service point (minimum valid)"
        base["ExpectedResult"] = "PASS"

    elif boundary_type == "ten_service_points":
        service_points = [generate_service_point() for _ in range(10)]
        base["ServicePoints"] = service_points_to_pipe_format(service_points)
        base["_servicePoints"] = service_points
        base["Description"] = "Boundary: 10 service points (typical maximum)"
        base["ExpectedResult"] = "PASS"

    elif boundary_type == "non_sepa_payment":
        base["Payment.Method"] = "BANK_TRANSFER"
        base["Payment.MandateReference"] = ""
        base["Payment.MandateSignatureDate"] = ""
        base["Description"] = "Boundary: non-SEPA payment (no mandate required)"
        base["ExpectedResult"] = "PASS"

    elif boundary_type == "special_characters":
        base["Contact.FullName"] = "Müller-Lüdenscheid, Dr. Günther"
        base["Organization.Name"] = "Größe & Söhne KG"
        base["Address.AddressLine1"] = "Königstraße"
        base["Description"] = "Boundary: German special characters (umlauts, ß)"
        base["ExpectedResult"] = "PASS"

    return base


def get_corpus_headers() -> list[str]:
    """Get the column headers for the corpus."""
    return [
        "TestCaseId",
        "TestType",
        "Description",
        "ExpectedResult",
        "ExecutionLog",
        "Record.SourceSystem",
        "Account.Number",
        "Contact.Email",
        "Contact.FullName",
        "Contact.Phone",
        "Contact.CallbackWindow",
        "Contact.PreferredChannel",
        "Contact.Timezone",
        "Organization.Name",
        "Organization.LegalForm",
        "Organization.OwnerName",
        "Address.AddressLine1",
        "Address.AddressLine2",
        "Address.HouseNumber",
        "Address.Additional",
        "Address.PostalCode",
        "Address.City",
        "Address.Region",
        "Address.Country",
        "Payment.IBAN",
        "Payment.BIC",
        "Payment.BookingText",
        "Payment.Schedule",
        "Payment.Currency",
        "Payment.Method",
        "Payment.MandateReference",
        "Payment.MandateSignatureDate",
        "Payer.Type",
        "Payer.FirstName",
        "Payer.LastName",
        "Payer.DateOfBirth",
        "ServicePoints",
    ]


def generate_test_cases(count: int) -> list[dict]:
    """Generate a mix of test cases."""
    test_cases = []
    test_id = 1

    # Distribution: ~60% valid, ~25% invalid, ~15% boundary
    num_valid = int(count * 0.6)
    num_invalid = int(count * 0.25)
    num_boundary = count - num_valid - num_invalid

    # Invalid types to cycle through
    invalid_types = [
        "zero_service_points",
        "invalid_iban",
        "missing_email",
        "missing_account_number",
        "missing_mandate_for_sepa",
        "invalid_email_format",
        "missing_fullname",
        "missing_organization_name",
    ]

    # Boundary types to cycle through
    boundary_types = [
        "eleven_service_points",
        "max_length_strings",
        "single_service_point",
        "ten_service_points",
        "non_sepa_payment",
        "special_characters",
    ]

    # Generate valid cases
    for _ in range(num_valid):
        test_cases.append(generate_valid_test_case(test_id))
        test_id += 1

    # Generate invalid cases
    for i in range(num_invalid):
        invalid_type = invalid_types[i % len(invalid_types)]
        test_cases.append(generate_invalid_test_case(test_id, invalid_type))
        test_id += 1

    # Generate boundary cases
    for i in range(num_boundary):
        boundary_type = boundary_types[i % len(boundary_types)]
        test_cases.append(generate_boundary_test_case(test_id, boundary_type))
        test_id += 1

    # Shuffle to mix case types
    random.shuffle(test_cases)

    # Renumber after shuffle
    for i, tc in enumerate(test_cases, 1):
        tc["TestCaseId"] = f"TC{i:03d}"

    return test_cases


def test_case_to_json_format(tc: dict) -> dict:
    """Convert test case to JSON output format with metadata/record/servicePoints structure."""
    metadata = {}
    record = {}

    for key, value in tc.items():
        if key == "_servicePoints":
            continue  # Skip internal field
        elif key in METADATA_KEYS:
            metadata[key] = value
        elif key == "ServicePoints":
            continue  # Use _servicePoints instead
        else:
            record[key] = value

    return {
        "metadata": metadata,
        "record": record,
        "servicePoints": tc.get("_servicePoints", []),
    }


def write_json_output(test_cases: list[dict], output_path: Optional[Path] = None):
    """Write test cases as JSON to file or stdout."""
    json_data = [test_case_to_json_format(tc) for tc in test_cases]

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
    else:
        # Write to stdout
        print(json.dumps(json_data, indent=2, ensure_ascii=False))


def write_xlsx_output(test_cases: list[dict], output_path: Path, append: bool = False):
    """Write test cases to Excel corpus file."""
    headers = get_corpus_headers()

    # Remove internal keys for xlsx output
    clean_cases = []
    for tc in test_cases:
        clean_tc = {k: v for k, v in tc.items() if not k.startswith("_")}
        clean_cases.append(clean_tc)

    if append and output_path.exists():
        wb = load_workbook(output_path)
        if "Synthetic" in wb.sheetnames:
            ws = wb["Synthetic"]
            # Find next test ID
            max_id = 0
            for row in ws.iter_rows(min_row=2, max_col=1, values_only=True):
                if row[0] and str(row[0]).startswith("TC"):
                    try:
                        num = int(str(row[0])[2:])
                        max_id = max(max_id, num)
                    except ValueError:
                        pass

            # Renumber and append
            for i, tc in enumerate(clean_cases, max_id + 1):
                tc["TestCaseId"] = f"TC{i:03d}"
                row_data = [tc.get(h, "") for h in headers]
                ws.append(row_data)
        else:
            ws = wb.create_sheet("Synthetic", 0)
            ws.append(headers)
            for tc in clean_cases:
                row_data = [tc.get(h, "") for h in headers]
                ws.append(row_data)
    else:
        wb = Workbook()

        # Create Synthetic sheet
        ws_synthetic = wb.active
        ws_synthetic.title = "Synthetic"
        ws_synthetic.append(headers)

        for tc in clean_cases:
            row_data = [tc.get(h, "") for h in headers]
            ws_synthetic.append(row_data)

        # Adjust column widths
        for i, header in enumerate(headers, 1):
            col_letter = get_column_letter(i)
            ws_synthetic.column_dimensions[col_letter].width = max(len(header) + 2, 15)

        # Create empty UAT sheet with headers
        ws_uat = wb.create_sheet("UAT")
        ws_uat.append(headers)

        for i, header in enumerate(headers, 1):
            col_letter = get_column_letter(i)
            ws_uat.column_dimensions[col_letter].width = max(len(header) + 2, 15)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    wb.close()


@app.command()
def main(
    count: Annotated[int, typer.Option("--count", "-n", help="Number of test cases to generate")] = 20,
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output file path (.xlsx or .json). Omit for stdout.")] = None,
    append: Annotated[bool, typer.Option("--append", "-a", help="Append to existing xlsx corpus")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be generated without writing")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress status messages (for piping)")] = False,
):
    """Generate synthetic test data for the data model.

    By default, outputs JSON to stdout for piping to other tools.
    Use --output to write to a file (.xlsx or .json).
    """
    def log(msg: str):
        if not quiet:
            print(msg, file=sys.stderr)

    log(f"Generating {count} test cases...")
    test_cases = generate_test_cases(count)

    # Summary
    valid_count = sum(1 for tc in test_cases if tc["TestType"] == "valid")
    invalid_count = sum(1 for tc in test_cases if tc["TestType"] == "invalid")
    boundary_count = sum(1 for tc in test_cases if tc["TestType"] == "boundary")

    log(f"Generated {len(test_cases)} test cases:")
    log(f"  - Valid: {valid_count}")
    log(f"  - Invalid: {invalid_count}")
    log(f"  - Boundary: {boundary_count}")

    if dry_run:
        log(f"\n[DRY RUN] Would output to: {output or 'stdout'}")
        if output:
            log(f"[DRY RUN] Format: {'xlsx' if str(output).endswith('.xlsx') else 'json'}")
            log(f"[DRY RUN] Mode: {'append' if append else 'overwrite'}")
        log("\nSample test cases:")
        for tc in test_cases[:3]:
            log(f"  {tc['TestCaseId']}: {tc['Description']} -> {tc['ExpectedResult']}")
        if len(test_cases) > 3:
            log(f"  ... and {len(test_cases) - 3} more")
        return

    if output:
        if str(output).endswith(".xlsx"):
            log(f"Writing xlsx to: {output}")
            write_xlsx_output(test_cases, output, append=append)
        else:
            log(f"Writing JSON to: {output}")
            write_json_output(test_cases, output)
        log("Done!")
    else:
        # Default: JSON to stdout
        write_json_output(test_cases)


if __name__ == "__main__":
    app()
