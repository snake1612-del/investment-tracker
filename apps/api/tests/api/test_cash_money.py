from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import get_uow_factory
from app.infrastructure.db.models import TransactionModel
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app

KINDS = ["withdrawals", "dividends", "coupons", "fees", "taxes"]
DAY = "2020-01-01"


@pytest.fixture
def client(clean_db: sessionmaker[Session]) -> Iterator[TestClient]:
    app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(clean_db)
    try:
        with TestClient(app, raise_server_exceptions=False) as value:
            yield value
    finally:
        app.dependency_overrides.clear()


def context(client: TestClient) -> tuple[int, int, int]:
    portfolio = client.post("/portfolios", json={"name": "Cash", "base_currency": "USD"}).json()[
        "id"
    ]
    account = client.post(f"/portfolios/{portfolio}/accounts", json={"name": "Journal"}).json()[
        "id"
    ]
    instrument = client.post("/instruments", json={"name": "Fund"}).json()["id"]
    return portfolio, account, instrument


def body(kind: str, instrument: int, **changes: object) -> dict[str, object]:
    facts: dict[str, object] = {"cash_amount": "1", "currency_code": "USD", "effective_date": DAY}
    if kind in {"dividends", "coupons", "buys", "sells"}:
        facts["instrument_id"] = instrument
    if kind in {"buys", "sells"}:
        facts.update(quantity="1", price="999", settlement_date=None)
    if kind in {"fees", "taxes"}:
        facts.update(instrument_id=None, related_transaction_id=None)
    return {**facts, **changes}


@pytest.mark.parametrize("kind", KINDS)
def test_create_correct_delete_all_new_types(
    client: TestClient,
    clean_db: sessionmaker[Session],
    kind: str,
) -> None:
    _, account, instrument = context(client)
    response = client.post(
        f"/accounts/{account}/{kind}", json=body(kind, instrument, note="Retained")
    )
    assert response.status_code == 201
    original = response.json()
    assert original["quantity"] is original["price"] is original["settlement_date"] is None
    with clean_db() as session:
        row = session.get(TransactionModel, original["id"])
        assert row is not None
        row.updated_at = datetime(2000, 1, 1, tzinfo=UTC)
        session.commit()
    url = f"/accounts/{account}/transactions/{original['id']}"
    before = datetime.now(UTC)
    corrected = client.put(
        url,
        json=body(
            kind, instrument, cash_amount="1E-8", currency_code="EUR", effective_date="2019-12-31"
        ),
    )
    assert corrected.status_code == 200
    record = corrected.json()
    for key in ("id", "account_id", "type", "created_at", "note"):
        assert record[key] == original[key]
    assert before <= datetime.fromisoformat(record["updated_at"]) <= datetime.now(UTC)
    assert Decimal(record["cash_amount"]) == Decimal("1E-8")
    before_invalid = client.get(f"/accounts/{account}/transactions").json()
    assert client.put(url, json=body(kind, instrument, cash_amount="0")).status_code == 422
    assert client.get(f"/accounts/{account}/transactions").json() == before_invalid
    assert client.delete(url).status_code == 204
    assert client.get(f"/accounts/{account}/transactions").json() == []


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "changes",
    [
        {"cash_amount": "0"},
        {"cash_amount": "-1"},
        {"cash_amount": "NaN"},
        {"cash_amount": "Infinity"},
        {"cash_amount": "bad"},
        {"cash_amount": "1E-9"},
        {"cash_amount": "10000000000000000"},
        {"currency_code": "usd"},
        {"quantity": "1"},
        {"price": "1"},
        {"settlement_date": None},
        {"type": "DEPOSIT"},
        {"account_id": 1},
        {"effective_date": "invalid"},
    ],
)
def test_create_rejection_has_no_persisted_effect(
    client: TestClient, kind: str, changes: dict
) -> None:
    _, account, instrument = context(client)
    assert (
        client.post(
            f"/accounts/{account}/{kind}", json=body(kind, instrument, **changes)
        ).status_code
        == 422
    )
    assert client.get(f"/accounts/{account}/transactions").json() == []


@pytest.mark.parametrize("kind", KINDS)
def test_missing_account_and_required_facts(client: TestClient, kind: str) -> None:
    _, account, instrument = context(client)
    facts = body(kind, instrument)
    assert client.post(f"/accounts/99999/{kind}", json=facts).status_code == 404
    created = client.post(f"/accounts/{account}/{kind}", json=facts).json()
    for key in facts:
        incomplete = {field: value for field, value in facts.items() if field != key}
        assert (
            client.put(
                f"/accounts/{account}/transactions/{created['id']}", json=incomplete
            ).status_code
            == 422
        )
    if kind in {"dividends", "coupons", "fees", "taxes"}:
        assert (
            client.post(
                f"/accounts/{account}/{kind}", json={**facts, "instrument_id": 99999}
            ).status_code
            == 404
        )


@pytest.mark.parametrize("kind", ["fees", "taxes"])
def test_relations_context_only_validation_and_clear(client: TestClient, kind: str) -> None:
    portfolio, account, instrument = context(client)
    other_instrument = client.post("/instruments", json={"name": "Other"}).json()["id"]
    other_account = client.post(f"/portfolios/{portfolio}/accounts", json={"name": "Other"}).json()[
        "id"
    ]
    parent = client.post(
        f"/accounts/{account}/dividends", json=body("dividends", instrument)
    ).json()
    wrong_parent = client.post(
        f"/accounts/{other_account}/deposits", json=body("deposits", instrument)
    ).json()
    for parent_id in (wrong_parent["id"], 99999):
        response = client.post(
            f"/accounts/{account}/{kind}",
            json=body(kind, instrument, related_transaction_id=parent_id),
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Related transaction not found"}
    assert (
        client.post(
            f"/accounts/{account}/{kind}",
            json=body(
                kind,
                instrument,
                instrument_id=other_instrument,
                related_transaction_id=parent["id"],
            ),
        ).status_code
        == 422
    )
    child = client.post(
        f"/accounts/{account}/{kind}",
        json=body(
            kind,
            instrument,
            instrument_id=instrument,
            related_transaction_id=parent["id"],
            currency_code="EUR",
        ),
    ).json()
    another = client.post(
        f"/accounts/{account}/{kind}",
        json=body(kind, instrument, related_transaction_id=parent["id"]),
    ).json()
    assert child["id"] != another["id"]
    for charge in ("fees", "taxes"):
        assert (
            client.post(
                f"/accounts/{account}/{charge}",
                json=body(charge, instrument, related_transaction_id=child["id"]),
            ).status_code
            == 422
        )
    url = f"/accounts/{account}/transactions/{child['id']}"
    snapshot = client.get(f"/accounts/{account}/transactions").json()
    assert (
        client.put(url, json=body(kind, instrument, related_transaction_id=child["id"])).status_code
        == 422
    )
    assert client.get(f"/accounts/{account}/transactions").json() == snapshot
    assert client.delete(f"/accounts/{account}/transactions/{parent['id']}").status_code == 409
    assert client.get(f"/accounts/{account}/transactions").json() == snapshot
    for parent_id in (wrong_parent["id"], 99999):
        assert (
            client.put(
                url, json=body(kind, instrument, related_transaction_id=parent_id)
            ).status_code
            == 404
        )
        assert client.get(f"/accounts/{account}/transactions").json() == snapshot
    assert (
        client.put(
            url,
            json=body(
                kind,
                instrument,
                instrument_id=other_instrument,
                related_transaction_id=parent["id"],
            ),
        ).status_code
        == 422
    )
    assert client.get(f"/accounts/{account}/transactions").json() == snapshot
    replacement = client.post(
        f"/accounts/{account}/coupons", json=body("coupons", instrument)
    ).json()
    changed = client.put(
        url,
        json=body(
            kind, instrument, instrument_id=instrument, related_transaction_id=replacement["id"]
        ),
    )
    assert (
        changed.status_code == 200 and changed.json()["related_transaction_id"] == replacement["id"]
    )
    cleared = client.put(url, json=body(kind, instrument))
    assert cleared.status_code == 200
    assert cleared.json()["instrument_id"] is cleared.json()["related_transaction_id"] is None
    assert client.delete(f"/accounts/{account}/transactions/{another['id']}").status_code == 204
    assert client.delete(f"/accounts/{account}/transactions/{parent['id']}").status_code == 204


def summary(client: TestClient, scope: str, day: str = DAY) -> dict:
    response = client.get(f"{scope}/money-summary", params={"as_of_date": day})
    assert response.status_code == 200
    return response.json()


def test_money_account_portfolio_currency_cutoff_and_gross_regression(client: TestClient) -> None:
    portfolio, account, instrument = context(client)
    other = client.post(f"/portfolios/{portfolio}/accounts", json={"name": "Independent"}).json()[
        "id"
    ]
    base = f"/accounts/{account}"
    assert summary(client, base) == {"as_of_date": DAY, "currencies": []}
    for kind in ("deposits", "withdrawals", "buys", "sells", "dividends", "coupons"):
        assert client.post(f"{base}/{kind}", json=body(kind, instrument)).status_code == 201
    gross_before = client.get(f"{base}/realised-pnl").json()
    for kind in ("fees", "taxes"):
        assert client.post(f"{base}/{kind}", json=body(kind, instrument)).status_code == 201
    assert client.get(f"{base}/realised-pnl").json() == gross_before
    zero = summary(client, base)["currencies"][0]
    assert zero["cash_balance"] == "0" and zero["gross_investment_income"] == "2"
    for value in zero.values():
        assert isinstance(value, str)
    tax = client.post(
        f"{base}/taxes", json=body("taxes", instrument, currency_code="EUR", cash_amount="1E-8")
    ).json()
    assert summary(client, base)["currencies"][0]["cash_balance"] == "-0.00000001"
    tax_url = f"{base}/transactions/{tax['id']}"
    assert (
        client.put(
            tax_url, json=body("taxes", instrument, cash_amount="2", currency_code="EUR")
        ).status_code
        == 200
    )
    assert summary(client, base)["currencies"][0]["taxes_paid_or_withheld"] == "2"
    assert client.get(f"{base}/realised-pnl").json() == gross_before
    assert client.delete(tax_url).status_code == 204
    assert client.get(f"{base}/realised-pnl").json() == gross_before
    client.post(
        f"/accounts/{other}/deposits",
        json=body("deposits", instrument, cash_amount="9999999999999999.99999999"),
    )
    client.post(
        f"/accounts/{other}/deposits", json=body("deposits", instrument, cash_amount="1E-8")
    )
    client.post(f"/accounts/{other}/taxes", json=body("taxes", instrument, currency_code="EUR"))
    total = summary(client, f"/portfolios/{portfolio}")
    assert [item["currency_code"] for item in total["currencies"]] == ["EUR", "USD"]
    assert total["currencies"][1]["cash_balance"] == "10000000000000000"
    assert summary(client, base, "2019-12-31")["currencies"] == []
    client.post(
        f"{base}/deposits",
        json=body("deposits", instrument, effective_date="2021-01-01", cash_amount="20"),
    )
    assert summary(client, base)["currencies"][0]["cash_balance"] == "0"
    assert summary(client, base, "2021-01-01")["currencies"][0]["cash_balance"] == "20"


@pytest.mark.parametrize("scope", ["accounts", "portfolios"])
def test_money_requires_explicit_date_and_existing_scope(client: TestClient, scope: str) -> None:
    portfolio, account, _ = context(client)
    identity = account if scope == "accounts" else portfolio
    url = f"/{scope}/{identity}/money-summary"
    assert client.get(url).status_code == 422
    assert client.get(url, params={"as_of_date": "bad"}).status_code == 422
    assert (
        client.get(f"/{scope}/99999/money-summary", params={"as_of_date": DAY}).status_code == 404
    )


def test_malformed_persisted_history_is_not_a_read_validation_error(
    client: TestClient,
    clean_db: sessionmaker[Session],
) -> None:
    _, account, instrument = context(client)
    transaction = client.post(
        f"/accounts/{account}/deposits", json=body("deposits", instrument)
    ).json()
    with clean_db() as session:
        row = session.get(TransactionModel, transaction["id"])
        assert row is not None
        # The broad persistence schema permits this source shape, but manual F008 rejects it.
        row.quantity = Decimal("1")
        session.commit()
    assert (
        client.get(f"/accounts/{account}/money-summary", params={"as_of_date": DAY}).status_code
        == 500
    )


@pytest.mark.parametrize("kind", ["fees", "taxes"])
def test_charge_mutations_recompute_money_but_never_gross_trade_pnl(
    client: TestClient, kind: str
) -> None:
    _, account, instrument = context(client)
    base = f"/accounts/{account}"
    client.post(f"{base}/buys", json=body("buys", instrument, cash_amount="10"))
    sale = client.post(f"{base}/sells", json=body("sells", instrument, cash_amount="15")).json()
    gross = client.get(f"{base}/realised-pnl").json()
    assert gross["resolved_pnl_by_currency"][0]["amount"] == {"numerator": "5", "denominator": "1"}
    charge = client.post(
        f"{base}/{kind}",
        json=body(kind, instrument, cash_amount="2", related_transaction_id=sale["id"]),
    ).json()
    assert summary(client, base)["currencies"][0]["cash_balance"] == "3"
    assert client.get(f"{base}/realised-pnl").json() == gross
    url = f"{base}/transactions/{charge['id']}"
    assert client.put(url, json=body(kind, instrument, cash_amount="4")).status_code == 200
    assert summary(client, base)["currencies"][0]["cash_balance"] == "1"
    assert client.get(f"{base}/realised-pnl").json() == gross
    assert client.delete(url).status_code == 204
    assert summary(client, base)["currencies"][0]["cash_balance"] == "5"
    assert client.get(f"{base}/realised-pnl").json() == gross
