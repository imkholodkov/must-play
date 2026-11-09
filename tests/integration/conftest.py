import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app


@pytest.fixture
def client(db_session):
    """HTTP-клиент, у которого API работает с тестовой сессией (транзакция откатится после теста)."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()
