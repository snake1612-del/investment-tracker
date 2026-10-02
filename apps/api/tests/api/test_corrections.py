from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import get_uow_factory
from app.infrastructure.db.models import TransactionModel
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app


@pytest.fixture
def client(clean_db: sessionmaker[Session]) -> Iterator[TestClient]:
    app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(clean_db)
    try:
        with TestClient(app) as value:
            yield value
    finally:
        app.dependency_overrides.clear()


def context(client: TestClient) -> tuple[int, int, int]:
    portfolio = client.post(
        "/portfolios", json={"name": "Corrections", "base_currency": "USD"}
    ).json()
    account = client.post(
        f"/portfolios/{portfolio['id']}/accounts", json={"name": "Journal"}
    ).json()
    instrument = client.post("/instruments", json={"name": "First"}).json()
    return portfolio["id"], account["id"], instrument["id"]


def body(instrument: int, **changes: object) -> dict[str, object]:
    return {
        "instrument_id": instrument,
        "effective_date": "2020-01-01",
        "currency_code": "USD",
        "quantity": "2",
        "price": "10",
        "cash_amount": "19",
        "settlement_date": None,
        **changes,
    }


@pytest.mark.parametrize("kind", ["deposits", "buys", "sells"])
def test_update_and_hard_delete_preserve_identity(
    client: TestClient,
    clean_db: sessionmaker[Session],
    kind: str,
) -> None:
    _, account, instrument = context(client)
    deposit = {"effective_date": "2020-01-01", "currency_code": "USD", "cash_amount": "19"}
    original = client.post(
        f"/accounts/{account}/{kind}",
        json={**(deposit if kind == "deposits" else body(instrument)), "note": "Keep this note"},
    ).json()
    parent = client.post(f"/accounts/{account}/deposits", json=deposit).json()
    with clean_db() as session:
        row = session.get(TransactionModel, original["id"])
        assert row is not None
        row.related_transaction_id = parent["id"]
        # A known old timestamp avoids elapsed-time/DB precision assumptions.
        row.updated_at = datetime(2000, 1, 1, tzinfo=UTC)
        session.commit()
    before = next(
        row
        for row in client.get(f"/accounts/{account}/transactions").json()
        if row["id"] == original["id"]
    )
    other = client.post("/instruments", json={"name": "Corrected"}).json()["id"]
    correction = (
        {**deposit, "cash_amount": "23", "currency_code": "EUR", "effective_date": "2019-12-31"}
        if kind == "deposits"
        else body(
            other,
            quantity="3",
            price="7",
            cash_amount="23",
            currency_code="EUR",
            effective_date="2019-12-31",
            settlement_date="2020-01-02",
        )
    )
    url = f"/accounts/{account}/transactions/{original['id']}"
    before_put = datetime.now(UTC)
    response = client.put(url, json=correction)
    assert response.status_code == 200
    updated = response.json()
    updated_at = datetime.fromisoformat(updated["updated_at"])
    assert updated_at.utcoffset() == timedelta(0)
    assert updated_at > datetime.fromisoformat(before["updated_at"])
    assert before_put <= updated_at <= datetime.now(UTC)
    with clean_db() as session:
        persisted = session.get(TransactionModel, original["id"])
        assert persisted is not None
        assert persisted.updated_at == updated_at
        assert persisted.created_at == datetime.fromisoformat(original["created_at"])
        assert persisted.effective_date.isoformat() == correction["effective_date"]
        assert persisted.currency_code == correction["currency_code"]
        assert persisted.cash_amount == Decimal("23")
    for field in ("id", "type", "account_id", "created_at", "note"):
        assert updated[field] == original[field]
    assert updated["related_transaction_id"] == parent["id"]
    assert Decimal(updated["cash_amount"]) == Decimal("23")
    assert updated["currency_code"] == "EUR"
    assert updated["effective_date"] == "2019-12-31"
    if kind != "deposits":
        assert updated["instrument_id"] == other
        assert Decimal(updated["quantity"]) == Decimal("3")
        assert Decimal(updated["price"]) == Decimal("7")
        assert updated["settlement_date"] == "2020-01-02"
        cleared = client.put(url, json={**correction, "settlement_date": None})
        assert cleared.status_code == 200
        assert cleared.json()["settlement_date"] is None
    deleted = client.delete(url)
    assert deleted.status_code == 204 and deleted.content == b""
    assert [row["id"] for row in client.get(f"/accounts/{account}/transactions").json()] == [
        parent["id"]
    ]
    with clean_db() as session:
        assert session.get(TransactionModel, original["id"]) is None
    assert client.delete(url).status_code == 404


@pytest.mark.parametrize("method", ["put", "delete"])
def test_wrong_account_and_missing_are_indistinguishable(client: TestClient, method: str) -> None:
    portfolio, account, instrument = context(client)
    other = client.post(f"/portfolios/{portfolio}/accounts", json={"name": "Other"}).json()["id"]
    trade = client.post(f"/accounts/{account}/buys", json=body(instrument)).json()

    def request(account_id: int, transaction_id: int):
        url = f"/accounts/{account_id}/transactions/{transaction_id}"
        return client.put(url, json=body(instrument)) if method == "put" else client.delete(url)

    wrong = request(other, trade["id"])
    missing = request(other, 99999)
    assert wrong.status_code == missing.status_code == 404
    assert wrong.json() == missing.json() == {"detail": "Transaction not found"}
    assert request(99999, trade["id"]).status_code == 404
    assert len(client.get(f"/accounts/{account}/transactions").json()) == 1


@pytest.mark.parametrize("kind", ["WITHDRAWAL", "DIVIDEND", "COUPON", "FEE", "TAX"])
def test_unsupported_types_not_mutable(
    client: TestClient,
    clean_db: sessionmaker[Session],
    kind: str,
) -> None:
    _, account, instrument = context(client)
    trade = client.post(f"/accounts/{account}/buys", json=body(instrument)).json()
    with clean_db() as session:
        row = session.get(TransactionModel, trade["id"])
        assert row is not None
        row.type = kind
        session.commit()
    url = f"/accounts/{account}/transactions/{trade['id']}"
    assert client.put(url, json=body(instrument)).status_code == 422
    assert client.delete(url).status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", "0"),
        ("price", "-1"),
        ("cash_amount", "0"),
        ("quantity", "1E-13"),
        ("price", "1E-13"),
        ("cash_amount", "1E-9"),
        ("cash_amount", "10000000000000000"),
        ("cash_amount", "NaN"),
        ("cash_amount", "bad"),
        ("currency_code", "usd"),
        ("effective_date", "not-a-date"),
        ("settlement_date", "2019-12-31"),
        ("type", "SELL"),
        ("account_id", 9),
        ("id", 9),
        ("note", "No"),
        ("related_transaction_id", 9),
    ],
)
def test_invalid_update_rolls_back(client: TestClient, field: str, value: object) -> None:
    _, account, instrument = context(client)
    original = client.post(f"/accounts/{account}/buys", json=body(instrument)).json()
    url = f"/accounts/{account}/transactions/{original['id']}"
    before = client.get(f"/accounts/{account}/transactions").json()
    assert client.put(url, json=body(instrument, **{field: value})).status_code == 422
    after = client.get(f"/accounts/{account}/transactions").json()
    assert after[0]["updated_at"] == before[0]["updated_at"]
    assert after == before


@pytest.mark.parametrize(
    "omitted",
    [
        "instrument_id",
        "effective_date",
        "currency_code",
        "quantity",
        "price",
        "cash_amount",
        "settlement_date",
    ],
)
def test_partial_put_rejected(client: TestClient, omitted: str) -> None:
    _, account, instrument = context(client)
    original = client.post(f"/accounts/{account}/buys", json=body(instrument)).json()
    correction = body(instrument)
    del correction[omitted]
    assert (
        client.put(
            f"/accounts/{account}/transactions/{original['id']}", json=correction
        ).status_code
        == 422
    )


def test_missing_instrument_and_wrong_request_shape(client: TestClient) -> None:
    _, account, instrument = context(client)
    buy = client.post(f"/accounts/{account}/buys", json=body(instrument)).json()
    assert (
        client.put(f"/accounts/{account}/transactions/{buy['id']}", json=body(99999)).status_code
        == 404
    )
    deposit = {"effective_date": "2020-01-01", "currency_code": "USD", "cash_amount": "1"}
    row = client.post(f"/accounts/{account}/deposits", json=deposit).json()
    assert (
        client.put(
            f"/accounts/{account}/transactions/{row['id']}", json=body(instrument)
        ).status_code
        == 422
    )
    assert (
        client.put(f"/accounts/{account}/transactions/{buy['id']}", json=deposit).status_code == 422
    )
    for bad in ({"cash_amount": "0"}, {"instrument_id": instrument}, {"note": "No"}):
        assert (
            client.put(
                f"/accounts/{account}/transactions/{row['id']}", json={**deposit, **bad}
            ).status_code
            == 422
        )


def test_canonical_relation_conflict_is_atomic(
    client: TestClient, clean_db: sessionmaker[Session]
) -> None:
    _, account, instrument = context(client)
    parent = client.post(f"/accounts/{account}/buys", json=body(instrument)).json()
    child = client.post(f"/accounts/{account}/sells", json=body(instrument)).json()
    with clean_db() as session:
        row = session.get(TransactionModel, child["id"])
        assert row is not None
        row.related_transaction_id = parent["id"]
        session.commit()
    response = client.delete(f"/accounts/{account}/transactions/{parent['id']}")
    assert response.status_code == 409
    assert response.json() == {"detail": "Persistence conflict"}
    with clean_db() as session:
        assert session.get(TransactionModel, parent["id"]) is not None
        row = session.get(TransactionModel, child["id"])
        assert row is not None and row.related_transaction_id == parent["id"]


def test_corrected_history_propagates_to_existing_engines(client: TestClient) -> None:
    portfolio, account, instrument = context(client)
    first = client.post(
        f"/accounts/{account}/buys", json=body(instrument, quantity="2", cash_amount="10")
    ).json()
    second = client.post(
        f"/accounts/{account}/buys",
        json=body(instrument, quantity="2", cash_amount="20", effective_date="2020-01-02"),
    ).json()
    sell = client.post(
        f"/accounts/{account}/sells",
        json=body(instrument, quantity="2", cash_amount="30", effective_date="2020-01-03"),
    ).json()
    base = f"/accounts/{account}"

    def pnl():
        return client.get(f"{base}/realised-pnl").json()

    def resolved():
        return pnl()["resolved_pnl_by_currency"][0]["amount"]

    assert resolved() == {"numerator": "20", "denominator": "1"}
    assert (
        client.put(
            f"{base}/transactions/{first['id']}",
            json=body(instrument, quantity="3", cash_amount="10"),
        ).status_code
        == 200
    )
    assert Decimal(client.get(f"{base}/positions").json()[0]["quantity"]) == Decimal("3")
    assert Decimal(
        client.get(f"/portfolios/{portfolio}/positions").json()[0]["quantity"]
    ) == Decimal("3")
    # Equal acquisition dates must retain the original ID tie-break.
    assert (
        client.put(
            f"{base}/transactions/{first['id']}",
            json=body(instrument, quantity="3", cash_amount="10", effective_date="2020-01-02"),
        ).status_code
        == 200
    )
    # Equal-date ordering still uses the preserved first ID, not a replacement ID.
    assert resolved() == {"numerator": "70", "denominator": "3"}
    assert (
        client.put(
            f"{base}/transactions/{first['id']}",
            json=body(instrument, quantity="3", cash_amount="10", effective_date="2020-01-03"),
        ).status_code
        == 200
    )
    assert resolved() == {"numerator": "10", "denominator": "1"}
    sell_correction = body(
        instrument, quantity="2", cash_amount="30", effective_date="2020-01-03", currency_code="EUR"
    )
    assert client.put(f"{base}/transactions/{sell['id']}", json=sell_correction).status_code == 200
    assert pnl()["unresolved_components"][0]["reason"] == "CURRENCY_MISMATCH"
    assert (
        client.put(
            f"{base}/transactions/{sell['id']}", json={**sell_correction, "currency_code": "USD"}
        ).status_code
        == 200
    )
    assert pnl()["is_fully_resolved"] is True
    assert client.delete(f"{base}/transactions/{second['id']}").status_code == 204
    assert client.delete(f"{base}/transactions/{first['id']}").status_code == 204
    assert pnl()["unresolved_components"][0]["reason"] == "MISSING_ACQUISITION_BASIS"
    assert client.delete(f"{base}/transactions/{sell['id']}").content == b""
    assert pnl()["resolved_pnl_by_currency"] == []
    assert pnl()["unresolved_components"] == []
    assert client.get(f"{base}/positions").json() == []


def test_instrument_correction_moves_canonical_acquisition(client: TestClient) -> None:
    _, account, instrument = context(client)
    other = client.post("/instruments", json={"name": "Correct instrument"}).json()["id"]
    buy = client.post(f"/accounts/{account}/buys", json=body(instrument)).json()
    client.post(f"/accounts/{account}/sells", json=body(instrument, effective_date="2020-01-02"))
    base = f"/accounts/{account}"
    assert client.get(f"{base}/realised-pnl").json()["is_fully_resolved"] is True
    assert client.put(f"{base}/transactions/{buy['id']}", json=body(other)).status_code == 200
    quantities = {
        row["instrument_id"]: Decimal(row["quantity"])
        for row in client.get(f"{base}/positions").json()
    }
    assert quantities == {instrument: Decimal("-2"), other: Decimal("2")}
    assert (
        client.get(f"{base}/realised-pnl").json()["unresolved_components"][0]["reason"]
        == "MISSING_ACQUISITION_BASIS"
    )
