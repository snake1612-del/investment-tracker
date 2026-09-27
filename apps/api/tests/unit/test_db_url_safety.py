import pytest

from tests.conftest import checked_test_urls

DEVELOPMENT_URL = (
    "postgresql+psycopg://investment_tracker:local_development_only"
    "@localhost:5432/investment_tracker"
)
TEST_URL = (
    "postgresql+psycopg://investment_tracker:local_development_only"
    "@localhost:5432/investment_tracker_test"
)


def test_normal_local_database_urls_are_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DEVELOPMENT_URL)
    monkeypatch.setenv("TEST_DATABASE_URL", TEST_URL)

    development, test = checked_test_urls()

    assert development.database == "investment_tracker"
    assert test.database == "investment_tracker_test"
    assert not development.query and not test.query


@pytest.mark.parametrize(
    "query",
    ["dbname=investment_tracker", "host=elsewhere.example", "arbitrary=value"],
)
def test_test_url_query_overrides_are_rejected_before_connection(
    monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", DEVELOPMENT_URL)
    monkeypatch.setenv("TEST_DATABASE_URL", f"{TEST_URL}?{query}")

    with pytest.raises(RuntimeError, match="query parameters"):
        checked_test_urls()


def test_development_url_query_overrides_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"{DEVELOPMENT_URL}?port=9999")
    monkeypatch.setenv("TEST_DATABASE_URL", TEST_URL)

    with pytest.raises(RuntimeError, match="query parameters"):
        checked_test_urls()
