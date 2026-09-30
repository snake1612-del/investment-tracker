from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import get_uow_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app


def trade_body(instrument_id: int) -> dict[str, int | str | None]:
    return {
        "instrument_id": instrument_id,
        "quantity": "2",
        "price": "10",
        "cash_amount": "19.99",
        "currency_code": "USD",
        "effective_date": "2020-01-02",
        "settlement_date": None,
    }


def test_manual_trade_api_flow(clean_db: sessionmaker[Session]) -> None:
    app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(clean_db)
    try:
        with TestClient(app) as client:
            first = client.post("/instruments", json={"name": "  Акция 東京  "})
            second = client.post("/instruments", json={"name": "Акция 東京"})
            assert first.status_code == second.status_code == 201
            assert first.json()["name"] == second.json()["name"] == "Акция 東京"
            assert first.json()["id"] != second.json()["id"]
            listed_instruments = client.get("/instruments")
            assert listed_instruments.status_code == 200
            assert [item["id"] for item in listed_instruments.json()] == [
                first.json()["id"],
                second.json()["id"],
            ]

            portfolio = client.post("/portfolios", json={"name": "Main", "base_currency": "USD"})
            account = client.post(
                f"/portfolios/{portfolio.json()['id']}/accounts", json={"name": "Broker"}
            )
            account_id = account.json()["id"]
            body = trade_body(first.json()["id"])
            buy = client.post(f"/accounts/{account_id}/buys", json=body)
            assert buy.status_code == 201
            assert buy.json()["type"] == "BUY"
            assert buy.json()["account_id"] == account_id
            assert buy.json()["instrument_id"] == first.json()["id"]
            assert buy.json()["related_transaction_id"] is None
            assert buy.json()["settlement_date"] is None
            assert buy.json()["effective_date"] == date(2020, 1, 2).isoformat()
            assert all(
                isinstance(buy.json()[field], str) for field in ("quantity", "price", "cash_amount")
            )
            assert Decimal(buy.json()["cash_amount"]) == Decimal("19.99")

            sell_body = {
                **body,
                "quantity": "3",
                "effective_date": "2019-01-02",
                "settlement_date": "2019-01-03",
            }
            sell = client.post(f"/accounts/{account_id}/sells", json=sell_body)
            assert sell.status_code == 201
            assert sell.json()["type"] == "SELL"
            assert sell.json()["settlement_date"] == "2019-01-03"
            assert isinstance(sell.json()["quantity"], str)
            assert Decimal(sell.json()["quantity"]) == Decimal("3")

            history = client.get(f"/accounts/{account_id}/transactions")
            assert history.status_code == 200
            assert [item["id"] for item in history.json()] == [buy.json()["id"], sell.json()["id"]]
            for history_row, created in zip(history.json(), (buy.json(), sell.json()), strict=True):
                for field in (
                    "id",
                    "account_id",
                    "instrument_id",
                    "related_transaction_id",
                    "type",
                    "currency_code",
                    "effective_date",
                    "settlement_date",
                    "note",
                ):
                    assert history_row[field] == created[field]
                for field in ("quantity", "price", "cash_amount"):
                    assert isinstance(history_row[field], str)
                    assert Decimal(history_row[field]) == Decimal(created[field])
            assert sell.json()["effective_date"] < buy.json()["effective_date"]
    finally:
        app.dependency_overrides.clear()


def test_manual_trade_api_errors(clean_db: sessionmaker[Session]) -> None:
    app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(clean_db)
    try:
        with TestClient(app) as client:
            for name in (" ", "x" * 201):
                assert client.post("/instruments", json={"name": name}).status_code == 422
            instrument = client.post("/instruments", json={"name": "Share"}).json()
            portfolio = client.post(
                "/portfolios", json={"name": "Main", "base_currency": "USD"}
            ).json()
            account = client.post(
                f"/portfolios/{portfolio['id']}/accounts", json={"name": "Broker"}
            ).json()
            url = f"/accounts/{account['id']}/buys"
            body = trade_body(instrument["id"])
            assert client.post("/accounts/999/buys", json=body).status_code == 404
            assert client.post(url, json={**body, "instrument_id": 999}).status_code == 404

            invalid: list[dict[str, int | str | None]] = [
                {"quantity": "0"},
                {"price": "-1"},
                {"cash_amount": "0"},
                {"currency_code": "usd"},
                {"settlement_date": "2020-01-01"},
                {"quantity": "not-decimal"},
                {"quantity": "1.0000000000001"},
                {"price": "1.0000000000001"},
                {"cash_amount": "1.000000001"},
                {"cash_amount": "10000000000000000"},
                {"type": "SELL"},
                {"fee": "1"},
            ]
            for override in invalid:
                assert client.post(url, json={**body, **override}).status_code == 422
            assert client.get(f"/accounts/{account['id']}/transactions").json() == []
    finally:
        app.dependency_overrides.clear()
