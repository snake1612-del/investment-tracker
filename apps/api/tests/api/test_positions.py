from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import get_uow_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app


def trade_body(
    instrument_id: int, quantity: str, effective_date: str = "2020-01-02"
) -> dict[str, str | int]:
    return {
        "instrument_id": instrument_id,
        "quantity": quantity,
        "price": "10",
        "cash_amount": "19.99",
        "currency_code": "USD",
        "effective_date": effective_date,
    }


def create_account(client: TestClient) -> int:
    portfolio = client.post("/portfolios", json={"name": "Main", "base_currency": "USD"})
    assert portfolio.status_code == 201
    account = client.post(f"/portfolios/{portfolio.json()['id']}/accounts", json={"name": "Broker"})
    assert account.status_code == 201
    return account.json()["id"]


def test_account_positions_real_persisted_api_flow(clean_db: sessionmaker[Session]) -> None:
    app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(clean_db)
    try:
        with TestClient(app) as client:
            account_id = create_account(client)
            url = f"/accounts/{account_id}/positions"
            assert client.get(url).json() == []
            assert client.get("/accounts/999/positions").status_code == 404

            first = client.post("/instruments", json={"name": "Same"}).json()["id"]
            second = client.post("/instruments", json={"name": "Same"}).json()["id"]
            zero = client.post("/instruments", json={"name": "Zero"}).json()["id"]

            operations = [
                ("buys", first, "1.123456789012", "2020-01-02"),
                ("buys", first, "2.000000000001", "2019-01-01"),
                ("buys", first, "100", "9999-01-01"),
                ("sells", second, "4", "2020-01-02"),
                ("buys", zero, "1", "2020-01-02"),
                ("sells", zero, "1", "2020-01-02"),
            ]
            for operation, instrument_id, quantity, effective_date in operations:
                created = client.post(
                    f"/accounts/{account_id}/{operation}",
                    json=trade_body(instrument_id, quantity, effective_date),
                )
                assert created.status_code == 201

            response = client.get(url)
            assert response.status_code == 200
            positions = response.json()
            assert [set(item) for item in positions] == [
                {"instrument_id", "instrument_name", "quantity"},
                {"instrument_id", "instrument_name", "quantity"},
            ]
            assert [item["instrument_id"] for item in positions] == [first, second]
            assert [item["instrument_name"] for item in positions] == ["Same", "Same"]
            assert all(isinstance(item["quantity"], str) for item in positions)
            assert Decimal(positions[0]["quantity"]) == Decimal("3.123456789013")
            assert Decimal(positions[1]["quantity"]) == Decimal("-4")
    finally:
        app.dependency_overrides.clear()


def test_malformed_persisted_trade_is_internal_error_not_422(
    clean_db: sessionmaker[Session],
) -> None:
    app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(clean_db)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            account_id = create_account(client)
            instrument_id = client.post("/instruments", json={"name": "Share"}).json()["id"]
            with clean_db.begin() as session:
                session.execute(
                    text(
                        "INSERT INTO transactions "
                        "(account_id, instrument_id, type, quantity, price, cash_amount, "
                        "currency_code, effective_date) "
                        "VALUES (:account_id, :instrument_id, 'BUY', NULL, 10, 20, "
                        "'USD', DATE '2020-01-02')"
                    ),
                    {"account_id": account_id, "instrument_id": instrument_id},
                )
            response = client.get(f"/accounts/{account_id}/positions")
            assert response.status_code == 500
            assert response.text == "Internal Server Error"
    finally:
        app.dependency_overrides.clear()
