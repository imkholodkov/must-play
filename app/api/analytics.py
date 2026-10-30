"""Аналитические эндпоинты: агрегации по жанрам, годам, расхождениям и изданиям."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.database import DbSession
from app.core.errors import AppError
from app.repositories import analytics as repo
from app.schemas.analytics import DivergenceItem, GenreStats, OutletStats, YearStats

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/genres", summary="Жанры: число игр, средний индекс, доля положительных и бесплатных")
def genres(db: DbSession, min_games: Annotated[int, Query(ge=1)] = 50) -> list[GenreStats]:
    return repo.genres_summary(db, min_games)


@router.get("/releases", summary="Динамика по годам: релизы, бесплатные, цена, средний индекс")
def releases(
    db: DbSession,
    year_from: Annotated[int, Query(ge=1970, le=2100)] = 2000,
    year_to: Annotated[int, Query(ge=1970, le=2100)] = 2025,
) -> list[YearStats]:
    if year_from > year_to:
        raise AppError("year_from должен быть не больше year_to")
    return repo.releases_by_year(db, year_from, year_to)


@router.get("/divergence", summary="Топ игр, где пресса и игроки расходятся сильнее всего")
def divergence(
    db: DbSession,
    kind: Literal["overrated", "underrated"] = "overrated",
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[DivergenceItem]:
    return repo.divergence_top(db, kind, limit)


@router.get("/outlets", summary="Строгость изданий: средняя оценка против средней по всем изданиям")
def outlets(
    db: DbSession,
    min_reviews: Annotated[int, Query(ge=1)] = 20,
    order: Literal["strict", "generous"] = "strict",
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[OutletStats]:
    return repo.outlets_strictness(db, min_reviews, limit, strict=order == "strict")
