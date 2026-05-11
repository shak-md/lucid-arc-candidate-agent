import base64
import io
import openpyxl
import pytest
from app.agent.file_parser import parse_and_validate


def make_xlsx(rows: list[list]) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def test_valid_records():
    content = make_xlsx([
        ["email", "first_name", "last_name"],
        ["alice@example.com", "Alice", "Smith"],
        ["bob@example.com", "Bob", "Jones"],
    ])
    result, warnings = parse_and_validate(content)
    assert result.valid_count == 2
    assert result.invalid_count == 0
    assert not warnings


def test_missing_email():
    content = make_xlsx([
        ["email", "first_name", "last_name"],
        ["", "Alice", "Smith"],
    ])
    result, warnings = parse_and_validate(content)
    assert result.valid_count == 0
    assert result.invalid_count == 1
    assert result.invalid_records[0].field == "email"
    assert "missing" in result.invalid_records[0].reason.lower()


def test_invalid_email_format():
    content = make_xlsx([
        ["email", "first_name", "last_name"],
        ["not-an-email", "Alice", "Smith"],
    ])
    result, warnings = parse_and_validate(content)
    assert result.invalid_count == 1
    assert "valid email" in result.invalid_records[0].reason.lower()


def test_missing_first_name():
    content = make_xlsx([
        ["email", "first_name", "last_name"],
        ["alice@example.com", "", "Smith"],
    ])
    result, warnings = parse_and_validate(content)
    assert result.invalid_count == 1
    assert result.invalid_records[0].field == "first_name"


def test_skips_empty_rows():
    content = make_xlsx([
        ["email", "first_name", "last_name"],
        ["alice@example.com", "Alice", "Smith"],
        [None, None, None],
    ])
    result, warnings = parse_and_validate(content)
    assert result.valid_count == 1
    assert result.total_rows == 1


def test_phone_optional():
    content = make_xlsx([
        ["email", "first_name", "last_name", "phone"],
        ["alice@example.com", "Alice", "Smith", "555-1234"],
    ])
    result, warnings = parse_and_validate(content)
    assert result.valid_count == 1
    assert result.valid_records[0].phone == "555-1234"


def test_mixed_valid_and_invalid():
    content = make_xlsx([
        ["email", "first_name", "last_name"],
        ["alice@example.com", "Alice", "Smith"],
        ["bad-email", "Bob", "Jones"],
        ["carol@example.com", "Carol", "White"],
    ])
    result, warnings = parse_and_validate(content)
    assert result.valid_count == 2
    assert result.invalid_count == 1


def test_empty_file_raises():
    content = make_xlsx([])
    with pytest.raises(ValueError, match="empty"):
        parse_and_validate(content)


def test_column_aliases():
    content = make_xlsx([
        ["Email Address", "First Name", "Last Name"],
        ["alice@example.com", "Alice", "Smith"],
    ])
    result, warnings = parse_and_validate(content)
    assert result.valid_count == 1
