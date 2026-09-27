from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import get_uow_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app


def test_persistence_api_flow(clean_db: sessionmaker[Session]) -> None:
    app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(clean_db)
    try:
        with TestClient(app) as client:
            portfolio = client.post("/portfolios", json={"name": "Main", "base_currency": "USD"})
            assert portfolio.status_code == 201
            portfolio_id = portfolio.json()["id"]

            account = client.post(f"/portfolios/{portfolio_id}/accounts", json={"name": "Broker"})
            assert account.status_code == 201
            account_id = account.json()["id"]

            deposit = client.post(
                f"/accounts/{account_id}/deposits",
                json={
                    "cash_amount": "100000.125",
                    "currency_code": "USD",
                    "effective_date": "2026-09-27",
                },
            )
            assert deposit.status_code == 201
            payload = deposit.json()
            assert isinstance(payload["cash_amount"], str)
            assert Decimal(payload["cash_amount"]) == Decimal("100000.125")
            assert payload["effective_date"] == date(2026, 9, 27).isoformat()
            assert payload["instrument_id"] is None

            listed = client.get(f"/accounts/{account_id}/transactions")
            assert listed.status_code == 200
            assert len(listed.json()) == 1
            assert listed.json()[0]["id"] == payload["id"]
            assert listed.json()[0]["type"] == "DEPOSIT"
            assert isinstance(listed.json()[0]["cash_amount"], str)
            assert Decimal(listed.json()[0]["cash_amount"]) == Decimal(payload["cash_amount"])
            assert listed.json()[0]["effective_date"] == payload["effective_date"]

            assert (
                client.post("/portfolios/999/accounts", json={"name": "Absent"}).status_code == 404
            )
            assert (
                client.post(
                    "/accounts/999/deposits",
                    json={
                        "cash_amount": "1",
                        "currency_code": "USD",
                        "effective_date": "2026-09-27",
                    },
                ).status_code
                == 404
            )
            assert client.get("/accounts/999/transactions").status_code == 404
            assert (
                client.post(
                    f"/accounts/{account_id}/deposits",
                    json={
                        "cash_amount": "0",
                        "currency_code": "USD",
                        "effective_date": "2026-09-27",
                    },
                ).status_code
                == 422
            )
    finally:
        app.dependency_overrides.clear()
