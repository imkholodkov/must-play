from pathlib import Path

import allure
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.database import Base

SAMPLE_CSV = Path(__file__).parent.parent / "data" / "sample" / "steam_games_sample.csv"

# Раздел отчёта Allure по имени тестового модуля
FEATURES = {
    "test_download_data": "ETL",
    "test_cleaning": "ETL",
    "test_transform": "ETL",
    "test_reviews": "ETL",
    "test_import_data": "ETL",
    "test_import_reviews": "ETL",
    "test_models": "База данных",
    "test_scoring": "Рейтинг",
    "test_rating": "Рейтинг",
    "test_health": "API",
    "test_api": "API",
    "test_analytics": "Аналитика",
    "test_recommendations": "Рекомендации",
    "test_ml_features": "ML",
    "test_ml_api": "ML",
}
LEVELS = {"unit": "Unit-тесты", "integration": "Интеграционные тесты"}


@pytest.fixture(autouse=True)
def allure_labels(request):
    """Разметить тест для Allure по папке и модулю, чтобы не размечать каждый тест вручную."""
    path = Path(request.node.fspath)
    feature = FEATURES.get(path.stem, path.stem)
    allure.dynamic.parent_suite(LEVELS.get(path.parent.name, path.parent.name))
    allure.dynamic.suite(feature)
    allure.dynamic.feature(feature)
    allure.dynamic.story(path.stem.removeprefix("test_"))


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
