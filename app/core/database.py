"""Подключение к БД и зависимость FastAPI для сессии."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

# Явные имена ограничений: Alembic сможет удалить их в downgrade
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# pool_pre_ping проверяет соединение перед запросом — переживёт перезапуск контейнера с БД
engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Отдать сессию на время запроса и закрыть её после."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# короткая запись для эндпоинтов: db: DbSession вместо Depends(get_db) в каждом
DbSession = Annotated[Session, Depends(get_db)]
