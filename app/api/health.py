"""Проверка, что сервис и БД доступны."""

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import DbSession

router = APIRouter(tags=["service"])


@router.get("/health", summary="Состояние сервиса и БД")
def health(db: DbSession) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "unavailable"
    return {"status": "ok", "database": database}
