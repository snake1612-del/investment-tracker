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


def setup(client):
    portfolio = client.post(
        "/portfolios", json={"name": "Performance synthetic", "base_currency": "USD"}
    ).json()["id"]
    account = client.post(f"/portfolios/{portfolio}/accounts", json={"name": "Broker"}).json()["id"]
    instrument = client.post("/instruments", json={"name": "Held"}).json()["id"]
    benchmark = client.post("/instruments", json={"name": "Global benchmark, not held"}).json()[
        "id"
    ]
    return portfolio, account, instrument, benchmark


def transaction(client, account, path, amount="100", day="2020-01-01", instrument=None):
    body = dict(cash_amount=amount, currency_code="USD", effective_date=day)
    if instrument is not None:
        body.update(instrument_id=instrument, quantity="1", price="999")
    result = client.post(f"/accounts/{account}/{path}", json=body)
    assert result.status_code == 201
    return result.json()


def observation(client, instrument, amount="100", day="2020-01-01", currency="USD"):
    result = client.post(
        f"/instruments/{instrument}/market-prices",
        json=dict(price=amount, currency_code=currency, effective_date=day),
    )
    assert result.status_code == 201
    return result.json()


def url(portfolio, benchmark=None):
    return f"/portfolios/{portfolio}/performance?start_date=2020-01-02&end_date=2020-01-03" + (
        f"&benchmark_instrument_id={benchmark}" if benchmark else ""
    )


def test_validation_and_no_public_account_or_daily_series(client):
    p, account, _, benchmark = setup(client)
    assert client.get(url(999)).status_code == 404
    assert client.get(url(p, 999)).status_code == 404
    for query in [
        "",
        "?start_date=2020-01-02",
        "?start_date=2020-01-04&end_date=2020-01-03",
        "?start_date=0001-01-01&end_date=2020-01-03",
        "?start_date=bad&end_date=2020-01-03",
    ]:
        assert client.get(f"/portfolios/{p}/performance{query}").status_code == 422
    assert (
        client.get(
            f"/accounts/{account}/performance?start_date=2020-01-02&end_date=2020-01-03"
        ).status_code
        == 404
    )
    assert client.get(f"/portfolios/{p}/performance/daily").status_code == 404
    result = client.get(url(p, benchmark)).json()
    assert result["performance"]["twr"] is None
    assert result["performance"]["unresolved_components"][0]["reason"] == "NO_CAPITAL_AT_RISK"
    assert (
        result["benchmark"]["unresolved_components"][0]["reason"]
        == "UNRESOLVED_PORTFOLIO_PERFORMANCE"
    )


def test_negative_opening_remains_unresolved_after_deposit(client):
    p, account, _, benchmark = setup(client)
    transaction(client, account, "withdrawals")
    transaction(client, account, "deposits", "200", "2020-01-02")
    response = client.get(url(p, benchmark))
    assert response.status_code == 200
    result = response.json()
    performance = result["performance"]
    assert performance["twr"] is None
    assert performance["is_fully_resolved"] is False
    diagnostic = performance["unresolved_components"][0]
    assert diagnostic["reason"] == "NEGATIVE_PERFORMANCE_VALUE"
    assert diagnostic["date"] == "2020-01-01"
    assert diagnostic["value"]["amount"] == dict(numerator="-100", denominator="1")
    assert diagnostic["capital_base"] is None
    assert result["benchmark"]["benchmark_twr"] is None
    assert result["benchmark"]["unresolved_components"][0]["reason"] == (
        "UNRESOLVED_PORTFOLIO_PERFORMANCE"
    )


def test_resolved_benchmark_and_backdated_price_transaction_correction(client):
    p, account, instrument, benchmark = setup(client)
    transaction(client, account, "deposits")
    buy = transaction(client, account, "buys", instrument=instrument)
    observation(client, instrument)
    price = observation(client, instrument, "110", "2020-01-03")
    observation(client, benchmark, "10")
    observation(client, benchmark, "12", "2020-01-03")
    result = client.get(url(p, benchmark)).json()
    assert result["performance"]["twr"] == dict(numerator="1", denominator="10")
    assert result["benchmark"]["benchmark_twr"] == dict(numerator="1", denominator="5")
    assert result["benchmark"]["active_return"] == dict(numerator="-1", denominator="10")
    assert result["benchmark"]["ending_value_difference"]["amount"] == dict(
        numerator="-10", denominator="1"
    )
    assert client.get(url(p)).json()["benchmark"] is None
    assert client.get(url(p, instrument)).json()["benchmark"]["active_return"]["numerator"] == "0"
    assert (
        client.put(
            f"/instruments/{instrument}/market-prices/{price['id']}",
            json=dict(price="120", currency_code="USD", effective_date="2020-01-03"),
        ).status_code
        == 200
    )
    assert client.get(url(p)).json()["performance"]["twr"] == dict(numerator="1", denominator="5")
    assert (
        client.put(
            f"/accounts/{account}/transactions/{buy['id']}",
            json=dict(
                instrument_id=instrument,
                quantity="1",
                price="999",
                cash_amount="90",
                currency_code="USD",
                effective_date="2020-01-01",
                settlement_date=None,
            ),
        ).status_code
        == 200
    )
    updated = client.get(url(p)).json()["performance"]
    assert updated["opening_value"]["amount"] == dict(numerator="110", denominator="1")
    assert updated["twr"] == dict(numerator="2", denominator="11")


def test_missing_history_date_diagnostics_and_zero_base_recovery(client):
    p, account, instrument, benchmark = setup(client)
    transaction(client, account, "deposits")
    buy = transaction(client, account, "buys", instrument=instrument)
    observation(client, instrument, "110", "2020-01-03")
    unresolved = client.get(url(p)).json()["performance"]
    assert unresolved["twr"] is None
    diagnostic = unresolved["unresolved_components"][0]
    assert diagnostic["date"] == "2020-01-01"
    assert diagnostic["instrument_name"] == "Held" and diagnostic["account_id"] == account
    assert client.delete(f"/accounts/{account}/transactions/{buy['id']}").status_code == 204
    observation(client, benchmark, "10")
    observation(client, benchmark, "0", "2020-01-02")
    observation(client, benchmark, "10", "2020-01-03")
    result = client.get(url(p, benchmark)).json()
    assert result["performance"]["twr"] == dict(numerator="0", denominator="1")
    b = result["benchmark"]
    assert b["benchmark_twr"] is None and b["active_return"] is None
    d = b["unresolved_components"][0]
    assert d["reason"] == "ZERO_CAPITAL_BASE_WITH_POSITIVE_VALUE"
    assert d["date"] == "2020-01-03"
    assert d["capital_base"]["amount"] == dict(numerator="0", denominator="1")
    assert d["value"]["amount"] == dict(numerator="100", denominator="1")
