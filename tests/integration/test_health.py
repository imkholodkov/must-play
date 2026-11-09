from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app


class BrokenSession:
    def execute(self, *args, **kwargs):
        from sqlalchemy.exc import OperationalError

        raise OperationalError("SELECT 1", {}, Exception("no db"))


class TestHealth:
    def test_health_reports_ok(self):
        response = TestClient(app).get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_reports_unavailable_database(self):
        app.dependency_overrides[get_db] = lambda: BrokenSession()
        try:
            response = TestClient(app).get("/health")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "unavailable"}


class TestUi:
    def test_root_redirects_to_ui(self):
        response = TestClient(app).get("/", follow_redirects=False)

        assert response.status_code == 307
        assert response.headers["location"] == "/ui/"

    def test_ui_served(self):
        client = TestClient(app)

        assert "Must Play" in client.get("/ui/").text
        assert client.get("/ui/app.js").status_code == 200
