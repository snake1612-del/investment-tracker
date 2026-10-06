from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import get_uow_factory
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


def setup(client: TestClient):
    portfolio = client.post(
        "/portfolios", json={"name": "Valuation", "base_currency": "USD"}
    ).json()["id"]
    account = client.post(f"/portfolios/{portfolio}/accounts", json={"name": "Broker"}).json()["id"]
    instrument = client.post("/instruments", json={"name": "Security"}).json()["id"]
    return portfolio, account, instrument


def observation(price: object = "20", day: str = "2020-01-02", currency: str = "USD"):
    return dict(price=price, currency_code=currency, effective_date=day)


def buy(client: TestClient, account: int, instrument: int):
    assert (
        client.post(
            f"/accounts/{account}/buys",
            json=dict(
                instrument_id=instrument,
                quantity="2",
                price="999",
                cash_amount="10",
                currency_code="USD",
                effective_date="2020-01-01",
            ),
        ).status_code
        == 201
    )


def test_price_lifecycle_ownership_conflict_and_metadata(client: TestClient):
    _, _, instrument = setup(client)
    path = f"/instruments/{instrument}/market-prices"
    first = client.post(path, json=observation("0")).json()
    assert first["price"] == "0"
    assert client.post(path, json=observation()).status_code == 409
    prior = client.post(path, json=observation("1", "2020-01-01")).json()
    assert [item["id"] for item in client.get(path).json()] == [first["id"], prior["id"]]
    assert (
        client.put(f"{path}/{first['id']}", json=observation(day="2020-01-01")).status_code == 409
    )
    assert client.get(path).json()[0] == first
    wrong = client.post("/instruments", json={"name": "Wrong"}).json()["id"]
    wrong_path = f"/instruments/{wrong}/market-prices/{first['id']}"
    assert client.put(wrong_path, json=observation()).status_code == 404
    assert client.delete(wrong_path).status_code == 404
    updated = client.put(
        f"{path}/{first['id']}", json=observation("0.123456789012", currency="EUR")
    ).json()
    assert updated["id"] == first["id"] and updated["instrument_id"] == instrument
    assert updated["created_at"] == first["created_at"]
    assert updated["updated_at"] > first["updated_at"]
    assert updated["price"] == "0.123456789012"
    assert client.delete(f"{path}/{first['id']}").status_code == 204
    assert client.delete(f"{path}/{first['id']}").status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        observation(-1),
        observation(1.2),
        observation("-1"),
        observation("NaN"),
        observation("1E-13"),
        observation(currency="usd"),
        {**observation(), "instrument_id": 1},
    ],
)
def test_strong_price_input(client: TestClient, body: dict):
    _, _, instrument = setup(client)
    assert client.post(f"/instruments/{instrument}/market-prices", json=body).status_code == 422


def test_backdated_correction_delete_fallback_and_required_date(client: TestClient):
    portfolio, account, instrument = setup(client)
    buy(client, account, instrument)
    path = f"/instruments/{instrument}/market-prices"
    prior = client.post(path, json=observation("3", "2020-01-01")).json()
    latest = client.post(path, json=observation()).json()
    endpoint = f"/accounts/{account}/valuation?as_of_date=2020-01-02"
    result = client.get(endpoint).json()
    assert result["metric"] == "SECURITY_VALUATION_AND_UNREALISED_PNL"
    assert result["resolved_market_value_by_currency"][0]["amount"] == {
        "numerator": "40",
        "denominator": "1",
    }
    assert result["resolved_unrealised_pnl_by_currency"][0]["amount"] == {
        "numerator": "30",
        "denominator": "1",
    }
    assert client.get(f"/portfolios/{portfolio}/valuation?as_of_date=2020-01-02").json() == result
    assert client.get(f"/accounts/{account}/valuation").status_code == 422
    assert client.get("/accounts/999/valuation?as_of_date=2020-01-02").status_code == 404
    assert client.put(f"{path}/{latest['id']}", json=observation("10")).status_code == 200
    assert (
        client.get(endpoint).json()["resolved_market_value_by_currency"][0]["amount"]["numerator"]
        == "20"
    )
    assert client.delete(f"{path}/{latest['id']}").status_code == 204
    assert (
        client.get(endpoint).json()["instruments"][0]["selected_market_price"]["effective_date"]
        == "2020-01-01"
    )
    assert client.delete(f"{path}/{prior['id']}").status_code == 204
    item = client.get(endpoint).json()["instruments"][0]
    assert item["market_value"] is None and item["selected_market_price"] is None
    assert item["unresolved_components"][0]["reason"] == "MISSING_MARKET_PRICE"


def test_portfolio_account_first_currency_mismatch_and_zero_price(client: TestClient):
    portfolio, account, instrument = setup(client)
    buy(client, account, instrument)
    second = client.post(f"/portfolios/{portfolio}/accounts", json={"name": "Second"}).json()["id"]
    assert (
        client.post(
            f"/accounts/{second}/sells",
            json=dict(
                instrument_id=instrument,
                quantity="2",
                price="1",
                cash_amount="1",
                currency_code="USD",
                effective_date="2020-01-01",
            ),
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/instruments/{instrument}/market-prices", json=observation("0", currency="EUR")
        ).status_code
        == 201
    )
    result = client.get(f"/portfolios/{portfolio}/valuation?as_of_date=2020-01-02").json()
    assert not result["is_fully_resolved"]
    assert len(result["instruments"]) == 2
    reasons = {
        component["reason"]
        for item in result["instruments"]
        for component in item["unresolved_components"]
    }
    assert reasons == {"CURRENCY_MISMATCH", "UNSUPPORTED_NEGATIVE_POSITION"}
    assert result["resolved_market_value_by_currency"][0]["amount"]["numerator"] == "0"
