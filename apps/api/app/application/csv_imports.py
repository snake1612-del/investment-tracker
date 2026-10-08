"""F012/Decision 023: exact normalized source parsing and atomic import."""

import csv
import hashlib
import io
import re
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import NoReturn

from app.application.contracts import CsvImportRecord
from app.application.use_cases import NotFound, UowFactory
from app.domain.transactions import CanonicalTransaction, InvalidTransaction, TransactionType

VERSION = "NORMALIZED_CSV_V1"
HEADER = (
    "row_id",
    "type",
    "effective_date",
    "settlement_date",
    "instrument_id",
    "quantity",
    "price",
    "cash_amount",
    "currency_code",
    "related_row_id",
    "note",
)
ROW_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
RECORD = re.compile(r'(?:[^",\r\n]*|"(?:[^"\r\n]|"")*")(?:,(?:[^",\r\n]*|"(?:[^"\r\n]|"")*"))*')
# Do not introduce csv.reader's implicit 128 KiB field cap into the approved
# contract. Transport limits still apply; this parser adds no note-size policy.
csv.field_size_limit(sys.maxsize)


@dataclass(frozen=True)
class Diagnostic:
    row_number: int | None
    row_id: str | None
    field: str
    code: str
    message: str


class InvalidCsv(ValueError):
    def __init__(self, diagnostics: list[Diagnostic]):
        self.diagnostics = diagnostics
        super().__init__("Invalid normalized CSV")


@dataclass(frozen=True)
class Source:
    rows: tuple[tuple[str, ...], ...]
    fingerprint: str


@dataclass(frozen=True)
class ValidatedRow:
    row_number: int
    row_id: str
    related_row_id: str | None
    fact: CanonicalTransaction


@dataclass(frozen=True)
class ImportResult:
    receipt: CsvImportRecord
    status: str


def parse_source(payload: bytes) -> Source:
    def fail(code: str, message: str, number: int | None = None) -> NoReturn:
        raise InvalidCsv([Diagnostic(number, None, "file", code, message)])

    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        fail("INVALID_ENCODING", "CSV must be UTF-8")
    lines = text.split("\n")
    physical_count = len(lines)
    if lines[-1] == "":
        lines.pop()
    parsed = []
    for number, raw in enumerate(lines, 1):
        line = raw[:-1] if raw.endswith("\r") and number < physical_count else raw
        if "\ufeff" in line or not RECORD.fullmatch(line):
            fail("INVALID_CSV", "Invalid quoting or embedded line break", number)
        if not line:
            fail(
                "INVALID_HEADER" if number == 1 else "INVALID_CSV",
                "Blank records are forbidden",
                number,
            )
        try:
            cells = tuple(next(csv.reader([line], strict=True)))
        except csv.Error, StopIteration:
            fail("INVALID_CSV", "Malformed CSV record", number)
        if number == 1:
            if cells != HEADER:
                fail("INVALID_HEADER", "Expected exact NORMALIZED_CSV_V1 header", number)
        elif len(cells) != len(HEADER):
            fail("INVALID_CSV", "Expected exactly 11 cells", number)
        else:
            parsed.append(cells)
    if not parsed:
        fail("EMPTY_IMPORT", "CSV contains no data rows")
    canonical = io.StringIO(newline="")
    writer = csv.writer(canonical, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(parsed)
    fingerprint = hashlib.sha256(
        (VERSION + "\n" + canonical.getvalue()).encode("utf-8")
    ).hexdigest()
    return Source(tuple(parsed), fingerprint)


def validate_rows(source: Source, account_id: int) -> tuple[list[ValidatedRow], list[Diagnostic]]:
    errors: list[Diagnostic] = []
    rows: list[ValidatedRow] = []
    seen = set()
    for number, cells in enumerate(source.rows, 2):
        values = dict(zip(HEADER, cells, strict=True))
        row_id = values["row_id"]
        start = len(errors)

        def error(field: str, code: str, message: str, number=number, row_id=row_id) -> None:
            errors.append(Diagnostic(number, row_id or None, field, code, message))

        if not ROW_ID.fullmatch(row_id):
            error(
                "row_id",
                "INVALID_ROW_ID",
                "Use 1..64 ASCII letters, digits, dot, underscore or hyphen",
            )
        if row_id in seen:
            error("row_id", "DUPLICATE_ROW_ID", "row_id must be unique within this file")
        seen.add(row_id)
        try:
            kind = TransactionType(values["type"])
        except ValueError:
            error("type", "INVALID_TRANSACTION", "Unsupported canonical Transaction type")
            continue
        required = {"effective_date", "cash_amount", "currency_code"}
        optional = {"note"}
        if kind in {TransactionType.BUY, TransactionType.SELL}:
            required |= {"instrument_id", "quantity", "price"}
            optional.add("settlement_date")
        elif kind in {TransactionType.DIVIDEND, TransactionType.COUPON}:
            required.add("instrument_id")
        elif kind in {TransactionType.FEE, TransactionType.TAX}:
            optional |= {"instrument_id", "related_row_id"}
        facts: dict = {"account_id": account_id}
        for field in HEADER[2:]:
            value = values[field]
            if not value:
                if field in required:
                    error(field, "MISSING_REQUIRED_FIELD", "Required for this Transaction type")
                continue
            if field not in required | optional:
                error(field, "FORBIDDEN_FIELD", "Must be empty for this Transaction type")
                continue
            if field in {"quantity", "price", "cash_amount"}:
                if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
                    error(
                        field,
                        "INVALID_DECIMAL",
                        "Use unsigned plain decimal text without whitespace",
                    )
                else:
                    facts[field] = Decimal(value)
            elif field in {"effective_date", "settlement_date"}:
                try:
                    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                        raise ValueError
                    facts[field] = date.fromisoformat(value)
                except ValueError:
                    error(field, "INVALID_DATE", "Use a valid YYYY-MM-DD date")
            elif field == "instrument_id":
                significant = value.lstrip("0")
                if (
                    not re.fullmatch(r"0*[1-9][0-9]*", value)
                    or len(significant) > 19
                    or int(significant) > 9223372036854775807
                ):
                    error(
                        field,
                        "INVALID_TRANSACTION",
                        "Use a positive canonical BIGINT Instrument ID",
                    )
                else:
                    facts[field] = int(significant)
            elif field == "related_row_id":
                if not ROW_ID.fullmatch(value):
                    error(field, "INVALID_ROW_ID", "Invalid related row identifier")
            else:
                facts[field] = value
        if len(errors) == start:
            try:
                constructor = getattr(CanonicalTransaction, kind.value.lower())
                fact = constructor(**facts)
                rows.append(ValidatedRow(number, row_id, values["related_row_id"] or None, fact))
            except InvalidTransaction as exc:
                field = next(
                    (
                        f
                        for f in [
                            "quantity",
                            "price",
                            "cash_amount",
                            "settlement_date",
                            "currency_code",
                        ]
                        if f in str(exc)
                    ),
                    "transaction",
                )
                error(field, "INVALID_TRANSACTION", str(exc))
    return rows, errors


def import_csv(factory: UowFactory, account_id: int, payload: bytes) -> ImportResult:
    source = parse_source(payload)
    with factory() as uow:
        if uow.accounts.get(account_id) is None:
            raise NotFound("Investment account not found")
        existing = uow.csv_imports.get(account_id, VERSION, source.fingerprint)
        if existing is not None:
            return ImportResult(existing, "ALREADY_IMPORTED")
        rows, errors = validate_rows(source, account_id)
        identifiers = {row.fact.instrument_id for row in rows if row.fact.instrument_id is not None}
        found = uow.instruments.existing_ids(identifiers)
        by_id = {row.row_id: row for row in rows}
        for row in rows:

            def error(field: str, code: str, message: str, row=row) -> None:
                errors.append(Diagnostic(row.row_number, row.row_id, field, code, message))

            if row.fact.instrument_id is not None and row.fact.instrument_id not in found:
                error("instrument_id", "INSTRUMENT_NOT_FOUND", "Instrument does not exist")
            if row.related_row_id:
                parent = by_id.get(row.related_row_id)
                if row.related_row_id == row.row_id:
                    error(
                        "related_row_id",
                        "RELATED_ROW_SELF_REFERENCE",
                        "A row cannot refer to itself",
                    )
                elif parent is None:
                    error(
                        "related_row_id",
                        "RELATED_ROW_NOT_FOUND",
                        "Parent must be a valid row in this CSV",
                    )
                elif parent.fact.type in {TransactionType.FEE, TransactionType.TAX}:
                    error(
                        "related_row_id",
                        "INVALID_RELATED_ROW_TYPE",
                        "Fee and Tax cannot be originating parents",
                    )
                elif (
                    row.fact.instrument_id is not None
                    and parent.fact.instrument_id is not None
                    and row.fact.instrument_id != parent.fact.instrument_id
                ):
                    error(
                        "related_row_id",
                        "RELATED_INSTRUMENT_MISMATCH",
                        "Child and parent Instruments must match",
                    )
        if errors:
            errors.sort(
                key=lambda e: (
                    e.row_number or 0,
                    HEADER.index(e.field) if e.field in HEADER else len(HEADER),
                    e.code,
                )
            )
            raise InvalidCsv(errors)
        receipt = uow.csv_imports.reserve(account_id, VERSION, source.fingerprint, len(rows))
        if receipt is None:
            existing = uow.csv_imports.get(account_id, VERSION, source.fingerprint)
            if existing is None:
                raise RuntimeError("Committed import reservation not found")
            return ImportResult(existing, "ALREADY_IMPORTED")
        transaction_ids = {}
        for row in rows:
            transaction_ids[row.row_id] = uow.transactions.add(row.fact).id
        for row in rows:
            if row.related_row_id:
                uow.transactions.finalize_import_relation(
                    transaction_ids[row.row_id], transaction_ids[row.related_row_id]
                )
        uow.commit()
        return ImportResult(receipt, "IMPORTED")
