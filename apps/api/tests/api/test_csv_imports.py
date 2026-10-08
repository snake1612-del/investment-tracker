from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.application.csv_imports import import_csv
from app.bootstrap import get_uow_factory
from app.infrastructure.db.models import CsvImportModel, TransactionModel
from app.infrastructure.db.repositories import (
    SqlAlchemyCsvImportRepository,
    SqlAlchemyTransactionRepository,
)
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app
from tests.unit.application.test_csv_imports import deposit, payload


@pytest.fixture
def context(clean_db):
    def factory():
        return SqlAlchemyUnitOfWork(clean_db)

    app.dependency_overrides[get_uow_factory] = lambda: factory
    try:
        with TestClient(app) as client:
            p = client.post(
                "/portfolios", json={"name": "CSV synthetic", "base_currency": "USD"}
            ).json()
            accounts = [
                client.post(f"/portfolios/{p['id']}/accounts", json={"name": str(n)}).json()["id"]
                for n in range(2)
            ]
            instruments = [
                client.post("/instruments", json={"name": str(n)}).json()["id"] for n in range(2)
            ]
            yield client, factory, accounts, instruments
    finally:
        app.dependency_overrides.clear()


def send(client, account, source):
    return client.post(
        f"/accounts/{account}/transaction-imports/csv",
        content=source,
        headers={"Content-Type": "text/csv; charset=utf-8"},
    )


def counts(factory):
    with factory() as uow:
        return tuple(
            uow.session.scalar(select(func.count()).select_from(model))
            for model in (TransactionModel, CsvImportModel)
        )


def test_all_types_order_relations_and_exactness(context):
    client, factory, accounts, instruments = context
    account, instrument = accounts[0], instruments[0]
    existing = client.post(
        f"/accounts/{account}/deposits",
        json={"cash_amount": "2", "currency_code": "USD", "effective_date": "2020-01-01"},
    ).json()
    rows = []
    # Child first, nonchronological dates, independent cash/price, oversell all stay valid.
    for n, kind in enumerate(
        ["FEE", "SELL", "DEPOSIT", "BUY", "TAX", "DIVIDEND", "COUPON", "WITHDRAWAL"]
    ):
        row = {
            **deposit(),
            "row_id": str(n),
            "type": kind,
            "note": str(n),
            "effective_date": "2020-01-02" if n == 0 else "2020-01-01",
        }
        if kind not in {"DEPOSIT", "WITHDRAWAL"}:
            row["instrument_id"] = str(instrument)
        if kind in {"BUY", "SELL"}:
            row.update(quantity="3.123456789012", price="9.987654321098")
        if kind in {"FEE", "TAX"}:
            row["related_row_id"] = "3"
        if kind == "COUPON":
            row["currency_code"] = "EUR"
        rows.append(row)
    response = send(client, account, payload(*rows))
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["status"] == "IMPORTED" and result["row_count"] == 8
    history = client.get(f"/accounts/{account}/transactions").json()
    assert history[0]["id"] == existing["id"]
    imported = history[1:]
    assert [t["note"] for t in imported] == list(map(str, range(8)))
    assert [t["id"] for t in history] == sorted(t["id"] for t in history)
    assert (
        imported[0]["related_transaction_id"]
        == imported[4]["related_transaction_id"]
        == imported[3]["id"]
    )
    assert imported[1]["quantity"] == "3.123456789012"
    assert imported[1]["cash_amount"] == "1.00000001"
    assert counts(factory) == (9, 1)
    for route in ["positions", "realised-pnl", "money-summary", "valuation"]:
        assert client.get(f"/accounts/{account}/{route}?as_of_date=2020-01-02").status_code == 200
    repeat = send(client, account, b"\xef\xbb\xbf" + payload(*rows, newline="\r\n"))
    assert repeat.status_code == 200
    assert repeat.json() == {**result, "status": "ALREADY_IMPORTED"}
    assert counts(factory) == (9, 1)
    assert send(client, accounts[1], payload(*rows)).status_code == 201
    assert counts(factory) == (17, 2)


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"cash_amount": "-1"}, "INVALID_DECIMAL"),
        ({"cash_amount": "0.000000001"}, "INVALID_TRANSACTION"),
        ({"instrument_id": "999999", "type": "DIVIDEND"}, "INSTRUMENT_NOT_FOUND"),
        ({"row_id": "one"}, "DUPLICATE_ROW_ID"),
        ({"type": "FEE", "related_row_id": "missing"}, "RELATED_ROW_NOT_FOUND"),
        ({"type": "FEE", "related_row_id": "two"}, "RELATED_ROW_SELF_REFERENCE"),
        ({"quantity": "1"}, "FORBIDDEN_FIELD"),
    ],
)
def test_invalid_whole_file_rolls_back(context, changes, code):
    client, factory, accounts, _ = context
    response = send(
        client, accounts[0], payload(deposit(), {**deposit(), "row_id": "two", **changes})
    )
    assert response.status_code == 422, response.text
    assert any(d["code"] == code and d["row_number"] == 3 for d in response.json()["detail"])
    assert counts(factory) == (0, 0)
    assert (
        send(
            client, accounts[0], payload(deposit(), {**deposit(), "row_id": "two", **changes})
        ).json()
        == response.json()
    )


@pytest.mark.parametrize(
    "parent_type,mismatch,code",
    [("FEE", False, "INVALID_RELATED_ROW_TYPE"), ("DIVIDEND", True, "RELATED_INSTRUMENT_MISMATCH")],
)
def test_invalid_relations(context, parent_type, mismatch, code):
    client, factory, accounts, instruments = context
    parent = {**deposit(), "type": parent_type, "instrument_id": str(instruments[0])}
    child = {
        **deposit(),
        "row_id": "child",
        "type": "TAX",
        "related_row_id": "one",
        "instrument_id": str(instruments[int(mismatch)]),
    }
    response = send(client, accounts[0], payload(parent, child))
    assert response.status_code == 422
    assert response.json()["detail"][0]["code"] == code
    assert counts(factory) == (0, 0)


def test_receipt_survives_correction_and_delete(context):
    client, factory, accounts, _ = context
    account = accounts[0]
    source = payload(deposit())
    original = send(client, account, source).json()
    transaction = client.get(f"/accounts/{account}/transactions").json()[0]
    url = f"/accounts/{account}/transactions/{transaction['id']}"
    assert (
        client.put(
            url, json={"effective_date": "2020-01-02", "cash_amount": "3", "currency_code": "USD"}
        ).status_code
        == 200
    )
    assert send(client, account, source).json()["status"] == "ALREADY_IMPORTED"
    assert client.delete(url).status_code == 204
    assert send(client, account, source).json() == {**original, "status": "ALREADY_IMPORTED"}
    assert counts(factory) == (0, 1)
    # Equal financial facts but distinct logical source remain separate imports.
    assert send(client, account, payload({**deposit(), "row_id": "changed"})).status_code == 201
    assert send(client, account, payload({**deposit(), "note": "new source"})).status_code == 201
    assert (
        send(client, account, payload({**deposit(), "cash_amount": "1.000000010"})).status_code
        == 201
    )
    assert counts(factory) == (3, 4)


def test_transport_and_missing_account(context):
    client, factory, accounts, _ = context
    assert send(client, 999999, payload(deposit())).status_code == 404
    assert (
        client.post(
            f"/accounts/{accounts[0]}/transaction-imports/csv", content=payload(deposit())
        ).status_code
        == 422
    )
    assert counts(factory) == (0, 0)


def test_duplicate_does_not_revalidate(context, monkeypatch):
    client, _, accounts, _ = context
    source = payload(deposit())
    assert send(client, accounts[0], source).status_code == 201

    def fail(*args):
        raise AssertionError("Committed sources must not be revalidated")

    monkeypatch.setattr("app.application.csv_imports.validate_rows", fail)
    assert send(client, accounts[0], source).status_code == 200


def test_concurrent_duplicate_one_batch(context, monkeypatch):
    _, factory, accounts, _ = context
    barrier = Barrier(2)
    original = SqlAlchemyCsvImportRepository.reserve

    def reserve(self, *args):
        barrier.wait(timeout=10)
        return original(self, *args)

    monkeypatch.setattr(SqlAlchemyCsvImportRepository, "reserve", reserve)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: import_csv(factory, accounts[0], payload(deposit())), range(2))
        )
    assert sorted(r.status for r in results) == ["ALREADY_IMPORTED", "IMPORTED"]
    assert results[0].receipt.id == results[1].receipt.id
    assert counts(factory) == (1, 1)


@pytest.mark.parametrize("stage", ["add", "relation", "commit"])
def test_persistence_failure_rolls_back_receipt_and_transactions(context, monkeypatch, stage):
    _, factory, accounts, _ = context

    def fail(*args):
        raise RuntimeError("Injected persistence failure")

    if stage == "commit":
        monkeypatch.setattr(SqlAlchemyUnitOfWork, "commit", fail)
    else:
        method = "add" if stage == "add" else "finalize_import_relation"
        original = getattr(SqlAlchemyTransactionRepository, method)

        def operation(self, *args):
            original(self, *args)
            fail()

        monkeypatch.setattr(SqlAlchemyTransactionRepository, method, operation)
    child = {**deposit(), "row_id": "child", "type": "FEE", "related_row_id": "one"}
    with pytest.raises(RuntimeError, match="Injected"):
        import_csv(factory, accounts[0], payload(deposit(), child))
    assert counts(factory) == (0, 0)


def test_backdated_import_reconstructs_positions(context):
    client, _, accounts, instruments = context
    account, instrument = accounts[0], instruments[0]
    sell = {
        **deposit(),
        "type": "SELL",
        "instrument_id": str(instrument),
        "quantity": "2",
        "price": "1",
        "effective_date": "2020-01-02",
    }
    assert send(client, account, payload(sell)).status_code == 201
    before = client.get(f"/accounts/{account}/realised-pnl?as_of_date=2020-01-02").json()
    buy = {**sell, "type": "BUY", "row_id": "buy", "effective_date": "2020-01-01"}
    assert send(client, account, payload(buy)).status_code == 201
    after = client.get(f"/accounts/{account}/realised-pnl?as_of_date=2020-01-02").json()
    assert before != after
    assert before["is_fully_resolved"] is False
    assert after["is_fully_resolved"] is True


def test_batch_instrument_lookup_and_one_commit(context, monkeypatch):
    _, factory, accounts, instruments = context
    queries = []
    engine = factory().session_factory.kw["bind"]

    def observe(connection, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    commits = []
    original = SqlAlchemyUnitOfWork.commit

    def commit(self):
        commits.append(True)
        original(self)

    monkeypatch.setattr(SqlAlchemyUnitOfWork, "commit", commit)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        rows = [
            {
                **deposit(),
                "row_id": str(n),
                "type": "DIVIDEND",
                "instrument_id": str(instruments[n % 2]),
            }
            for n in range(10)
        ]
        import_csv(factory, accounts[0], payload(*rows))
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert len([q for q in queries if q.startswith("SELECT") and "FROM instruments" in q]) == 1
    assert commits == [True]
    assert counts(factory) == (10, 1)


def test_duplicate_id_diagnostics_keep_physical_line_numbers(context):
    client, factory, accounts, _ = context
    row = {**deposit(), "type": "DIVIDEND", "instrument_id": "999999"}
    response = send(client, accounts[0], payload(row, row))
    assert response.status_code == 422
    assert any(
        d["code"] == "INSTRUMENT_NOT_FOUND" and d["row_number"] == 2
        for d in response.json()["detail"]
    )
    assert counts(factory) == (0, 0)
