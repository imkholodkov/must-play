from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.database import Base

SAMPLE_CSV = Path(__file__).parent.parent / "data" / "sample" / "steam_games_sample.csv"


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(get_settings().database_url)
    try:
        engine.connect().close()
    except OperationalError:
        pytest.skip("PostgreSQL недоступен: тесты с БД пропущены")
    return engine


@pytest.fixture
def db_session(engine):
    """Сессия в транзакции, которая откатывается после теста: база остаётся чистой.

    Схема создаётся внутри той же транзакции, так что тесты работают и на пустой БД.
    """
    connection = engine.connect()
    transaction = connection.begin()
    Base.metadata.create_all(connection)
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()
