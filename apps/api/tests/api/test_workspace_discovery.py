from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import get_uow_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app


def test_workspace_discovery(clean_db: sessionmaker[Session]) -> None:
    app.dependency_overrides[get_uow_factory] = lambda: lambda: SqlAlchemyUnitOfWork(clean_db)
    try:
        with TestClient(app) as client:
            assert client.get("/portfolios").json() == []
            first = client.post("/portfolios", json={"name": "Z", "base_currency": "USD"}).json()
            second = client.post("/portfolios", json={"name": "A", "base_currency": "EUR"}).json()
            listed = client.get("/portfolios")
            assert listed.status_code == 200
            assert listed.json() == [first, second]
            path = f"/portfolios/{first['id']}/accounts"
            assert client.get(path).json() == []
            account1 = client.post(path, json={"name": "Z"}).json()
            account2 = client.post(path, json={"name": "A"}).json()
            other = f"/portfolios/{second['id']}/accounts"
            account3 = client.post(other, json={"name": "Z"}).json()
            response = client.get(path)
            assert response.status_code == 200
            assert response.json() == [account1, account2]
            assert client.get(other).json() == [account3]
            assert client.get("/portfolios/999999/accounts").status_code == 404
            assert client.get(path).json() == response.json()
    finally:
        app.dependency_overrides.clear()
