import sys
from collections.abc import Iterator
from datetime import date
from decimal import Context, Decimal, localcontext
from fractions import Fraction
from math import gcd, isqrt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import get_uow_factory
from app.domain.portfolio.engine.exact import scaled_int_to_decimal
from app.domain.transactions import CanonicalTransaction
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app

METRIC = "GROSS_TRADE_CASH_REALISED_PNL"


@pytest.fixture
def client(clean_db: sessionmaker[Session]) -> Iterator[TestClient]:
    app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(clean_db)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def portfolio(client: TestClient) -> int:
    response = client.post("/portfolios", json={"name": "Main", "base_currency": "USD"})
    assert response.status_code == 201
    return response.json()["id"]


def account(client: TestClient, portfolio_id: int) -> int:
    response = client.post(f"/portfolios/{portfolio_id}/accounts", json={"name": "Broker"})
    assert response.status_code == 201
    return response.json()["id"]


def instrument(client: TestClient) -> int:
    response = client.post("/instruments", json={"name": "Same display name"})
    assert response.status_code == 201
    return response.json()["id"]


def trade(
    client: TestClient,
    account_id: int,
    instrument_id: int,
    operation: str,
    quantity: str,
    cash: str,
    currency: str = "USD",
    day: str = "2020-01-01",
) -> int:
    response = client.post(
        f"/accounts/{account_id}/{operation}",
        json={
            "instrument_id": instrument_id,
            "quantity": quantity,
            "price": "999",  # Independent factual price, deliberately not cash / quantity.
            "cash_amount": cash,
            "currency_code": currency,
            "effective_date": day,
            "settlement_date": "2099-01-01",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def money(currency: str, numerator: str, denominator: str = "1") -> dict[str, object]:
    return {
        "currency_code": currency,
        "amount": {"numerator": numerator, "denominator": denominator},
    }


def read(client: TestClient, resource: str, id_: int) -> dict:
    response = client.get(f"/{resource}/{id_}/realised-pnl")
    assert response.status_code == 200
    result = response.json()
    assert set(result) == {
        "metric",
        "resolved_pnl_by_currency",
        "unresolved_components",
        "is_fully_resolved",
    }
    assert result["metric"] == METRIC
    for item in result["resolved_pnl_by_currency"]:
        assert_canonical_money(item)
    for item in result["unresolved_components"]:
        assert "realised_pnl" not in item and "source_buy_transaction_id" not in item
        assert isinstance(item["quantity"], str)
        assert_canonical_money(item["allocated_proceeds"])
        if item["reason"] == "CURRENCY_MISMATCH":
            assert_canonical_money(item["removed_basis"])
        else:
            assert "removed_basis" not in item
    return result


def assert_canonical_money(item: dict) -> None:
    assert set(item) == {"currency_code", "amount"}
    assert set(item["amount"]) == {"numerator", "denominator"}
    n, d = item["amount"]["numerator"], item["amount"]["denominator"]
    assert isinstance(n, str) and isinstance(d, str)
    value = Fraction(int(n), int(d))
    assert int(d) > 0
    assert (n, d) == (str(value.numerator), str(value.denominator))


def test_empty_buy_only_and_missing_resources(client: TestClient) -> None:
    p = portfolio(client)
    a = account(client, p)
    empty = {
        "metric": METRIC,
        "resolved_pnl_by_currency": [],
        "unresolved_components": [],
        "is_fully_resolved": True,
    }
    assert read(client, "accounts", a) == read(client, "portfolios", p) == empty
    assert read(client, "portfolios", portfolio(client)) == empty
    trade(client, a, instrument(client), "buys", "3", "100")
    assert read(client, "accounts", a) == read(client, "portfolios", p) == empty
    for resource in ("accounts", "portfolios"):
        response = client.get(f"/{resource}/999/realised-pnl")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


@pytest.mark.parametrize(
    ("buy_quantity", "buy_cash", "sell_cash", "numerator", "denominator"),
    [
        ("1", "80", "100", "20", "1"),
        ("1", "100", "80", "-20", "1"),
        ("1", "100", "100", "0", "1"),
        ("3", "200", "100", "100", "3"),
        ("1", "0.00000001", "9999999999999999.99999999", "499999999999999999999999", "50000000"),
    ],
)
def test_exact_resolved_profit_loss_zero_repeating_and_large_values(
    client: TestClient,
    buy_quantity: str,
    buy_cash: str,
    sell_cash: str,
    numerator: str,
    denominator: str,
) -> None:
    p = portfolio(client)
    a = account(client, p)
    i = instrument(client)
    trade(client, a, i, "buys", buy_quantity, buy_cash)
    trade(client, a, i, "sells", "1", sell_cash)
    with localcontext(Context(prec=3)):
        result = read(client, "accounts", a)
        assert result == read(client, "portfolios", p)
    assert result == {
        "metric": METRIC,
        "resolved_pnl_by_currency": [money("USD", numerator, denominator)],
        "unresolved_components": [],
        "is_fully_resolved": True,
    }


def test_partial_sell_discriminated_shapes_and_same_sell_order(client: TestClient) -> None:
    p = portfolio(client)
    a = account(client, p)
    i = instrument(client)
    trade(client, a, i, "buys", "1", "10", "USD")
    trade(client, a, i, "buys", "1", "20", "EUR")
    trade(client, a, i, "buys", "1", "30", "GBP")
    sell = trade(client, a, i, "sells", "4", "100", day="2020-01-02")
    result = read(client, "accounts", a)
    assert result == read(client, "portfolios", p)
    assert result["resolved_pnl_by_currency"] == [money("USD", "15")]
    assert result["is_fully_resolved"] is False
    base = {
        "account_id": a,
        "sell_transaction_id": sell,
        "instrument_id": i,
        "instrument_name": "Same display name",
        "effective_date": "2020-01-02",
        "quantity": "1.000000000000",
        "allocated_proceeds": money("USD", "25"),
    }
    assert result["unresolved_components"] == [
        {**base, "reason": "CURRENCY_MISMATCH", "removed_basis": money("EUR", "20")},
        {**base, "reason": "CURRENCY_MISMATCH", "removed_basis": money("GBP", "30")},
        {**base, "reason": "MISSING_ACQUISITION_BASIS"},
    ]


def test_currency_mismatch_is_200_with_both_exact_legs(client: TestClient) -> None:
    p = portfolio(client)
    a = account(client, p)
    i = instrument(client)
    trade(client, a, i, "buys", "3", "100", "EUR")
    sell = trade(client, a, i, "sells", "1", "100", "USD")
    result = read(client, "accounts", a)
    assert result["resolved_pnl_by_currency"] == []
    assert result["is_fully_resolved"] is False
    assert result["unresolved_components"] == [
        {
            "reason": "CURRENCY_MISMATCH",
            "account_id": a,
            "sell_transaction_id": sell,
            "instrument_id": i,
            "instrument_name": "Same display name",
            "effective_date": "2020-01-01",
            "quantity": "1.000000000000",
            "allocated_proceeds": money("USD", "100"),
            "removed_basis": money("EUR", "100", "3"),
        }
    ]


def test_portfolio_isolation_multicurrency_exact_aggregation_and_order(client: TestClient) -> None:
    p = portfolio(client)
    a, b = account(client, p), account(client, p)
    unused_basis_account = account(client, p)
    other = account(client, portfolio(client))
    i = instrument(client)
    j = instrument(client)  # Duplicate display names are not identities.
    trade(client, unused_basis_account, j, "buys", "10", "100", day="2018-01-01")
    trade(client, a, i, "buys", "3", "200")
    trade(client, a, i, "sells", "1", "100")  # USD 100/3
    trade(client, b, i, "buys", "3", "200")
    trade(client, b, i, "sells", "1", "100")  # USD 100/3 independently
    trade(client, b, j, "buys", "1", "10", "EUR")
    trade(client, b, j, "sells", "1", "10", "EUR")  # Exact zero stays present.
    late = trade(client, b, j, "sells", "1", "40", day="2020-01-03")
    early = trade(client, a, j, "sells", "0.000000000001", "20", day="2019-01-01")
    same_day = trade(client, a, j, "sells", "1", "30", day="2020-01-03")
    trade(client, other, i, "buys", "10", "1000")
    trade(client, other, i, "sells", "10", "2000")
    result = read(client, "portfolios", p)
    assert result["resolved_pnl_by_currency"] == [money("EUR", "0"), money("USD", "200", "3")]
    assert result["is_fully_resolved"] is False
    assert [
        (item["sell_transaction_id"], item["account_id"])
        for item in result["unresolved_components"]
    ] == [
        (early, a),
        (late, b),
        (same_day, a),
    ]
    assert Decimal(result["unresolved_components"][0]["quantity"]) == Decimal("1E-12")
    assert all(
        item["reason"] == "MISSING_ACQUISITION_BASIS" for item in result["unresolved_components"]
    )
    assert read(client, "accounts", a)["resolved_pnl_by_currency"] == [money("USD", "100", "3")]
    assert read(client, "accounts", b)["resolved_pnl_by_currency"] == [
        money("EUR", "0"),
        money("USD", "100", "3"),
    ]


@pytest.mark.parametrize("resource", ["accounts", "portfolios"])
def test_malformed_persisted_history_is_internal_failure(
    client: TestClient,
    clean_db: sessionmaker[Session],
    resource: str,
) -> None:
    p = portfolio(client)
    a = account(client, p)
    i = instrument(client)
    with clean_db.begin() as session:
        session.execute(
            text(
                "INSERT INTO transactions "
                "(account_id, instrument_id, type, quantity, price, cash_amount, "
                "currency_code, effective_date) "
                "VALUES (:a, :i, 'SELL', NULL, 10, 20, 'USD', DATE '2020-01-01')"
            ),
            {"a": a, "i": i},
        )
    response = client.get(f"/{resource}/{a if resource == 'accounts' else p}/realised-pnl")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"


def test_openapi_exposes_reason_discriminator_not_nullable_financial_fields(
    client: TestClient,
) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    items = schemas["RealisedPnlRead"]["properties"]["unresolved_components"]["items"]
    items = schemas[items["$ref"].rsplit("/", 1)[1]]
    assert items["discriminator"]["propertyName"] == "reason"
    assert len(items["oneOf"]) == 2
    assert "removed_basis" in schemas["CurrencyMismatchRead"]["required"]
    assert "removed_basis" not in schemas["MissingAcquisitionBasisRead"]["properties"]
    for name in ("CurrencyMismatchRead", "MissingAcquisitionBasisRead"):
        assert "realised_pnl" not in schemas[name]["properties"]


def test_account_and_portfolio_arbitrary_size_rational_from_valid_persisted_history(
    client: TestClient,
    clean_db: sessionmaker[Session],
) -> None:
    limit_before = sys.get_int_max_str_digits()
    assert limit_before == sys.int_info.default_max_str_digits == 4300
    p = portfolio(client)
    a = account(client, p)
    primes: list[int] = []
    candidate = 100000001
    while len(primes) < 600:
        if all(candidate % divisor for divisor in range(3, isqrt(candidate) + 1, 2)):
            primes.append(candidate)
        candidate += 2

    # Genuine canonical transactions, real repositories and PostgreSQL. Only setup is batched.
    with SqlAlchemyUnitOfWork(clean_db) as uow:
        for index, prime in enumerate(primes):
            i = uow.instruments.add(f"Rational regression {index}").id
            uow.transactions.add(
                CanonicalTransaction.buy(
                    a,
                    i,
                    scaled_int_to_decimal(prime, 12),
                    Decimal("999"),
                    Decimal("1"),
                    "USD",
                    date(2020, 1, 1),
                )
            )
            uow.transactions.add(
                CanonicalTransaction.sell(
                    a,
                    i,
                    Decimal("1E-12"),
                    Decimal("999"),
                    Decimal("1"),
                    "USD",
                    date(2020, 1, 2),
                )
            )
        uow.commit()

    # Independent financial expectation: each disposed basis is exactly 1 / prime USD.
    expected = Fraction(len(primes)) - sum((Fraction(1, prime) for prime in primes), Fraction(0))
    with pytest.raises(ValueError, match="limit"):
        str(expected.numerator)
    with pytest.raises(ValueError, match="limit"):
        str(expected.denominator)

    def parse_decimal_string(value: str) -> int:
        # Independent oracle; never parse or format an oversized int in one conversion.
        assert value and value[0] in "123456789"
        parsed = 0
        for digit in value:
            assert "0" <= digit <= "9"
            parsed = parsed * 10 + ord(digit) - ord("0")
        return parsed

    results = []
    for resource, id_ in [("accounts", a), ("portfolios", p)]:
        response = client.get(f"/{resource}/{id_}/realised-pnl")
        assert response.status_code == 200
        result = response.json()
        assert set(result) == {
            "metric",
            "resolved_pnl_by_currency",
            "unresolved_components",
            "is_fully_resolved",
        }
        assert result["metric"] == METRIC
        assert result["is_fully_resolved"] is True
        assert result["unresolved_components"] == []
        assert len(result["resolved_pnl_by_currency"]) == 1
        item = result["resolved_pnl_by_currency"][0]
        assert set(item) == {"currency_code", "amount"}
        assert item["currency_code"] == "USD"
        assert set(item["amount"]) == {"numerator", "denominator"}
        n, d = item["amount"]["numerator"], item["amount"]["denominator"]
        assert isinstance(n, str) and isinstance(d, str)
        assert len(n) > 4300 and len(d) > 4300
        numerator, denominator = parse_decimal_string(n), parse_decimal_string(d)
        assert numerator == expected.numerator
        assert denominator == expected.denominator
        assert denominator > 0 and gcd(numerator, denominator) == 1
        results.append(result)
    assert results[0] == results[1]
    assert sys.get_int_max_str_digits() == limit_before
