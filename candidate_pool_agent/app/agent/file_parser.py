import base64
import io
import re
import openpyxl
from typing import Tuple
from app.models.schemas import CandidateRecord, ValidationError, ParseResult

REQUIRED_FIELDS = {"email", "first_name", "last_name"}
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

COLUMN_ALIASES = {
    "email": ["email", "email address", "e-mail"],
    "first_name": ["first_name", "first name", "firstname"],
    "last_name": ["last_name", "last name", "lastname", "surname"],
    "phone": ["phone", "phone number", "mobile", "telephone"],
}


def _normalize_header(header: str) -> str:
    return str(header).strip().lower().replace("-", "_")


def _map_headers(raw_headers: list) -> dict:
    """Map spreadsheet column headers to normalized field names."""
    column_map = {}
    for idx, raw in enumerate(raw_headers):
        normalized = _normalize_header(raw)
        for field, aliases in COLUMN_ALIASES.items():
            if normalized in aliases:
                column_map[field] = idx
                break
    return column_map


def _validate_record(
    row_number: int,
    email: str | None,
    first_name: str | None,
    last_name: str | None,
) -> list[ValidationError]:
    errors = []

    if not email or not email.strip():
        errors.append(ValidationError(
            row_number=row_number,
            field="email",
            reason="Email is required but missing",
        ))
    elif not EMAIL_REGEX.match(email.strip()):
        errors.append(ValidationError(
            row_number=row_number,
            field="email",
            reason=f"'{email.strip()}' is not a valid email address",
        ))

    if not first_name or not first_name.strip():
        errors.append(ValidationError(
            row_number=row_number,
            field="first_name",
            reason="First name is required but missing",
        ))

    if not last_name or not last_name.strip():
        errors.append(ValidationError(
            row_number=row_number,
            field="last_name",
            reason="Last name is required but missing",
        ))

    return errors


def parse_and_validate(file_content_base64: str) -> Tuple[ParseResult, list[str]]:
    """
    Decode a base64-encoded xlsx file, parse candidate rows, and validate each one.
    Returns a ParseResult and a list of any structural warnings (e.g. missing columns).
    """
    warnings = []

    try:
        file_bytes = base64.b64decode(file_content_base64)
        workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        sheet = workbook.active
    except Exception as e:
        raise ValueError(f"Could not open file: {str(e)}")

    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("The file appears to be empty.")

    raw_headers = rows[0]
    column_map = _map_headers(raw_headers)

    for required in REQUIRED_FIELDS:
        if required not in column_map:
            warnings.append(f"Expected column '{required}' not found. Check that your export includes email, first name, and last name columns.")

    valid_records = []
    invalid_records = []

    for row_idx, row in enumerate(rows[1:], start=2):
        def get_cell(field: str) -> str | None:
            idx = column_map.get(field)
            if idx is None:
                return None
            val = row[idx] if idx < len(row) else None
            return str(val).strip() if val is not None else None

        email = get_cell("email")
        first_name = get_cell("first_name")
        last_name = get_cell("last_name")
        phone = get_cell("phone")

        # Skip completely empty rows
        if not any([email, first_name, last_name]):
            continue

        errors = _validate_record(row_idx, email, first_name, last_name)

        if errors:
            invalid_records.extend(errors)
        else:
            valid_records.append(CandidateRecord(
                row_number=row_idx,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
            ))

    total_rows = len(valid_records) + len(
        {e.row_number for e in invalid_records}
    )

    return ParseResult(
        valid_records=valid_records,
        invalid_records=invalid_records,
        total_rows=total_rows,
        valid_count=len(valid_records),
        invalid_count=len({e.row_number for e in invalid_records}),
    ), warnings
