from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import get_uow_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app


def create_portfolio(client: TestClient, name: str) -> int:
    response = client.post("/portfolios", json={"name": name, "base_currency": "USD"})
    assert response.status_code == 201
    return response.json()["id"]


def create_account(client: TestClient, portfolio_id: int) -> int:
    response = client.post(f"/portfolios/{portfolio_id}/accounts", json={"name": "Broker"})
    assert response.status_code == 201
    return response.json()["id"]


def create_instrument(client: TestClient, name: str) -> int:
    response = client.post("/instruments", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def trade(
    client: TestClient,
    account_id: int,
    operation: str,
    instrument_id: int,
    quantity: str,
    effective_date: str = "2020-01-02",
    settlement_date: str | None = None,
) -> None:
    response = client.post(
        f"/accounts/{account_id}/{operation}",
        json={
            "instrument_id": instrument_id,
            "quantity": quantity,
            "price": "10",
            "cash_amount": "19.99",
            "currency_code": "USD",
            "effective_date": effective_date,
            "settlement_date": settlement_date,
        },
    )
    assert response.status_code == 201


def test_portfolio_positions_persisted_flow_and_isolation(clean_db: sessionmaker[Session]) -> None:
    app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(clean_db)
    try:
        with TestClient(app) as client:
            portfolio_id = create_portfolio(client, "Main")
            empty_id = create_portfolio(client, "Empty")
            other_id = create_portfolio(client, "Other")
            first_account = create_account(client, portfolio_id)
            second_account = create_account(client, portfolio_id)
            create_account(client, portfolio_id)  # Account without trades.
            other_account = create_account(client, other_id)

            assert client.get(f"/portfolios/{empty_id}/positions").json() == []
            assert client.get("/portfolios/999/positions").status_code == 404

            first = create_instrument(client, "ABC")
            second = create_instrument(client, "ABC")
            zero = create_instrument(client, "Zero")
            negative = create_instrument(client, "Negative")

            trade(client, first_account, "buys", first, "1.123456789012")
            trade(
                client,
                second_account,
                "buys",
                first,
                "2.000000000001",
                effective_date="2019-01-01",
                settlement_date="2099-01-01",
            )
            trade(client, first_account, "buys", second, "10")
            trade(client, second_account, "sells", second, "4")
            trade(client, first_account, "buys", zero, "10")
            trade(client, second_account, "sells", zero, "10")
            trade(client, second_account, "sells", negative, "4")
            trade(client, first_account, "buys", first, "100", effective_date="9999-01-01")
            trade(client, other_account, "buys", first, "999")

            response = client.get(f"/portfolios/{portfolio_id}/positions")
            assert response.status_code == 200
            positions = response.json()
            assert [set(item) for item in positions] == [
                {"instrument_id", "instrument_name", "quantity"}
            ] * 3
            assert [item["instrument_id"] for item in positions] == [first, second, negative]
            assert [item["instrument_name"] for item in positions] == ["ABC", "ABC", "Negative"]
            assert all(isinstance(item["quantity"], str) for item in positions)
            assert [Decimal(item["quantity"]) for item in positions] == [
                Decimal("3.123456789013"),
                Decimal("6"),
                Decimal("-4"),
            ]

            account_response = client.get(f"/accounts/{first_account}/positions")
            assert account_response.status_code == 200
            assert [item["instrument_id"] for item in account_response.json()] == [
                first,
                second,
                zero,
            ]
            assert all(set(item) == set(positions[0]) for item in account_response.json())
    finally:
        app.dependency_overrides.clear()


def test_only_zero_final_portfolio_positions_return_empty(clean_db: sessionmaker[Session]) -> None:
    app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(clean_db)
    try:
        with TestClient(app) as client:
            portfolio_id = create_portfolio(client, "Main")
            first_account = create_account(client, portfolio_id)
            second_account = create_account(client, portfolio_id)
            instrument_id = create_instrument(client, "Share")
            trade(client, first_account, "buys", instrument_id, "10")
            trade(client, second_account, "sells", instrument_id, "10")
            response = client.get(f"/portfolios/{portfolio_id}/positions")
            assert response.status_code == 200
            assert response.json() == []
    finally:
        app.dependency_overrides.clear()


def test_malformed_portfolio_history_is_internal_error_not_422(
    clean_db: sessionmaker[Session],
) -> None:
    app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(clean_db)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            portfolio_id = create_portfolio(client, "Main")
            account_id = create_account(client, portfolio_id)
            instrument_id = create_instrument(client, "Share")
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
            response = client.get(f"/portfolios/{portfolio_id}/positions")
            assert response.status_code == 500
            assert response.text == "Internal Server Error"
    finally:
        app.dependency_overrides.clear()
