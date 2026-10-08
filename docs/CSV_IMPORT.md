# Normalized CSV Import v0.1

Select an Account → Import CSV → choose a UTF-8 CSV → Import. The browser sends
one raw file request and refreshes History and derived reads after success.
Use synthetic files during testing; never commit financial CSVs.

`POST /accounts/{account_id}/transaction-imports/csv`

`Content-Type: text/csv; charset=utf-8`

Exact header/order:

```csv
row_id,type,effective_date,settlement_date,instrument_id,quantity,price,cash_amount,currency_code,related_row_id,note
deposit-1,DEPOSIT,2020-01-01,,,,,100.00,USD,,Synthetic opening cash
```

Use existing canonical Instrument IDs for trades and income. Fee/Tax Instrument
and intra-file `related_row_id` are optional; the parent may occur anywhere in the
file, but must not be Fee/Tax or the row itself. Do not use database Transaction
IDs as related-row references. Instrument identities must agree when both rows
specify one. Create/select Instruments separately before importing.

F012 and Decision 023 are authoritative for all eight types and required/forbidden
cells. Dates are exact `YYYY-MM-DD`; numeric cells are unsigned plain decimal text
(no signs, exponent, whitespace or locale separators), using existing canonical
positivity/precision rules. Quantity, price and trade cash remain independent.
Notes accept Unicode and standard comma/quote escaping, not embedded CR/LF.
No header changes, extra columns, blank records, partial import or matching guesses.

Results: `201 IMPORTED` or `200 ALREADY_IMPORTED`, with `import_id`,
`format_version`, `source_fingerprint`, `row_count`. Invalid files return `422`
and deterministic `detail` diagnostics (`row_number`, `row_id`, `field`, `code`,
`message`). Physical line numbers include the header as line 1. Missing Account
uses 404; unexpected persistence failures never commit a partial batch.

Source identity is SHA-256 of UTF-8 `NORMALIZED_CSV_V1\n` followed by canonical
CSV (exact header, parsed strings, comma, minimal quoting/doubled quotes, LF,
including a final LF). BOM/CRLF/equivalent quoting do not change identity.
No field normalization: `1.0` and `1.00`, notes, row IDs and row order do change it.
Receipts are Account-scoped and remain after corrections/deletions. Re-upload does
not recreate deleted rows; there is no force re-import. Equal financial facts from
different sources are not deduplicated.

All inserts preserve physical data-row order; later-parent relations finalize
before the single commit. Backdated and oversell history is allowed. Derived
results are recomputed, not stored. Migration `0003_csv_imports` adds only receipt
metadata and is applied to cloud databases only through explicit operator rollout.
