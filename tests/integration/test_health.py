from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app


class BrokenSession:
    def execute(self, *args, **kwargs):
        from sqlalchemy.exc import OperationalError

        raise OperationalError("SELECT 1", {}, Exception("no db"))


def test_health_reports_ok():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_unavailable_database():
    app.dependency_overrides[get_db] = lambda: BrokenSession()
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "unavailable"}
