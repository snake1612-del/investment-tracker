import csv
import io
from decimal import Decimal
from typing import Literal

import pytest

from app.application.csv_imports import HEADER, InvalidCsv, parse_source, validate_rows


def payload(*rows, newline="\n", quoting: Literal[0, 1] = csv.QUOTE_MINIMAL):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator=newline, quoting=quoting)
    writer.writerow(HEADER)
    for row in rows:
        writer.writerow([row.get(field, "") for field in HEADER])
    return output.getvalue().encode("utf-8")


def deposit(**changes):
    return dict(
        row_id="one",
        type="DEPOSIT",
        effective_date="2020-01-01",
        cash_amount="1.00000001",
        currency_code="USD",
        **changes,
    )


def test_logical_fingerprint_and_exact_values():
    row = deposit(note='Exact, "東京"')
    first = parse_source(payload(row))
    for source in [
        payload(row, newline="\r\n"),
        payload(row, quoting=csv.QUOTE_ALL),
        b"\xef\xbb\xbf" + payload(row),
        payload(row).rstrip(b"\n"),
    ]:
        assert parse_source(source) == first
    rows, errors = validate_rows(first, 9)
    assert errors == []
    assert rows[0].fact.cash_amount == Decimal("1.00000001")
    assert rows[0].fact.account_id == 9
    assert rows[0].fact.note == 'Exact, "東京"'


@pytest.mark.parametrize(
    "field,value", [("row_id", "two"), ("note", "changed"), ("cash_amount", "1.000000010")]
)
def test_source_text_changes_fingerprint(field, value):
    row = deposit()
    assert (
        parse_source(payload(row)).fingerprint
        != parse_source(payload({**row, field: value})).fingerprint
    )


def test_row_order_changes_fingerprint():
    one, two = deposit(), {**deposit(), "row_id": "two"}
    assert (
        parse_source(payload(one, two)).fingerprint != parse_source(payload(two, one)).fingerprint
    )


@pytest.mark.parametrize(
    "source",
    [
        b"\xff",
        b"wrong\n",
        payload(),
        payload(deposit()) + b"\n",
        payload(deposit(note="line\nbreak")),
        payload(deposit(note="line\rbreak")),
        payload(deposit()).replace(b"one,", b'one",'),
        payload(deposit()).replace(b"USD,", b"USD,extra,"),
        payload(deposit()).replace(b"row_id,type", b"type,row_id"),
    ],
)
def test_invalid_structure(source):
    with pytest.raises(InvalidCsv):
        parse_source(source)


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("cash_amount", "1e2", "INVALID_DECIMAL"),
        ("cash_amount", "-1", "INVALID_DECIMAL"),
        ("cash_amount", "+1", "INVALID_DECIMAL"),
        ("cash_amount", " 1", "INVALID_DECIMAL"),
        ("cash_amount", ".1", "INVALID_DECIMAL"),
        ("cash_amount", "NaN", "INVALID_DECIMAL"),
        ("cash_amount", "0", "INVALID_TRANSACTION"),
        ("cash_amount", "0.000000001", "INVALID_TRANSACTION"),
        ("currency_code", "usd", "INVALID_TRANSACTION"),
        ("effective_date", "2020-1-1", "INVALID_DATE"),
        ("effective_date", "2020-02-30", "INVALID_DATE"),
        ("cash_amount", "", "MISSING_REQUIRED_FIELD"),
        ("instrument_id", "1", "FORBIDDEN_FIELD"),
        ("row_id", " spaced ", "INVALID_ROW_ID"),
        ("row_id", "я", "INVALID_ROW_ID"),
        ("type", "deposit", "INVALID_TRANSACTION"),
    ],
)
def test_strict_row_validation(field, value, code):
    _, errors = validate_rows(parse_source(payload({**deposit(), field: value})), 1)
    assert any(error.code == code for error in errors)
    assert all(error.row_number == 2 for error in errors)


def test_duplicate_row_id():
    _, errors = validate_rows(parse_source(payload(deposit(), deposit())), 1)
    assert [(error.row_number, error.code) for error in errors] == [(3, "DUPLICATE_ROW_ID")]


@pytest.mark.parametrize(
    "kind", ["DEPOSIT", "WITHDRAWAL", "BUY", "SELL", "DIVIDEND", "COUPON", "FEE", "TAX"]
)
def test_all_types_use_canonical_validation(kind):
    row = {**deposit(), "type": kind}
    if kind in {"BUY", "SELL", "DIVIDEND", "COUPON"}:
        row["instrument_id"] = "1"
    if kind in {"BUY", "SELL"}:
        row.update(quantity="1.123456789012", price="2.987654321098", settlement_date="2020-01-02")
    rows, errors = validate_rows(parse_source(payload(row)), 1)
    assert not errors
    assert rows[0].fact.type.value == kind
    assert rows[0].fact.cash_amount == Decimal("1.00000001")


@pytest.mark.parametrize("kind", ["DEPOSIT", "WITHDRAWAL", "DIVIDEND", "COUPON", "FEE", "TAX"])
@pytest.mark.parametrize("field", ["quantity", "price", "settlement_date"])
def test_non_trade_fields_are_forbidden(kind, field):
    row = {**deposit(), "type": kind, field: "1"}
    if kind in {"DIVIDEND", "COUPON"}:
        row["instrument_id"] = "1"
    _, errors = validate_rows(parse_source(payload(row)), 1)
    assert any(e.field == field and e.code == "FORBIDDEN_FIELD" for e in errors)


@pytest.mark.parametrize("kind", ["BUY", "SELL", "DIVIDEND", "COUPON"])
def test_instrument_is_required(kind):
    _, errors = validate_rows(parse_source(payload({**deposit(), "type": kind})), 1)
    assert any(e.field == "instrument_id" and e.code == "MISSING_REQUIRED_FIELD" for e in errors)


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", "0.0000000000001"),
        ("price", "10000000000000000"),
        ("cash_amount", "10000000000000000"),
    ],
)
def test_unrepresentable_trade_facts_are_rejected(field, value):
    row = {
        **deposit(),
        "type": "BUY",
        "instrument_id": "1",
        "quantity": "1",
        "price": "1",
        field: value,
    }
    _, errors = validate_rows(parse_source(payload(row)), 1)
    assert any(e.field == field and e.code == "INVALID_TRANSACTION" for e in errors)


def test_note_whitespace_is_preserved_and_empty_is_absent():
    for note, expected in [("  unchanged  ", "  unchanged  "), ("", None)]:
        rows, errors = validate_rows(parse_source(payload(deposit(note=note))), 1)
        assert not errors
        assert rows[0].fact.note == expected


def test_long_note_has_no_implicit_csv_library_field_limit():
    note = "x" * 150000
    rows, errors = validate_rows(parse_source(payload(deposit(note=note))), 1)
    assert not errors
    assert rows[0].fact.note == note
