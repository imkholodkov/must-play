"""Рейтинг всех времён, must play и запуск пересчёта."""

from typing import Annotated

from fastapi import APIRouter, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import DbSession
from app.core.errors import ConflictError
from app.models import Game, GameScore, MustPlayEntry, RatingRun
from app.repositories.games import GameFilters, SortField, list_games
from app.schemas.common import Page
from app.schemas.game import GameRead
from app.services.rating import RatingInProgressError, recalculate

router = APIRouter(tags=["rating"])


class RatingRunRead(BaseModel):
    id: int
    status: str
    games_scored: int


class MustPlayItem(GameRead):
    must_play_status: str


@router.get("/rating", summary="Рейтинг всех времён: допущенные игры по убыванию индекса")
def rating(
    db: DbSession,
    genre: Annotated[str | None, Query(examples=["RPG"])] = None,
    decade: Annotated[int | None, Query(ge=1970, le=2020, multiple_of=10, description="Десятилетие: 2010")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[GameRead]:
    filters = GameFilters(genre=genre, eligible=True)
    if decade:
        filters.year_from, filters.year_to = decade, decade + 9
    items, total = list_games(db, filters, SortField.index, True, limit, offset)
    return Page[GameRead](items=items, total=total, limit=limit, offset=offset)


@router.get("/must-play", summary="Список must play: игры в статусе in_list по убыванию индекса")
def must_play(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[GameRead]:
    base = (
        select(Game)
        .join(MustPlayEntry, MustPlayEntry.app_id == Game.app_id)
        .join(GameScore, GameScore.app_id == Game.app_id)
        .where(MustPlayEntry.status == "in_list")
    )
    total = len(db.scalars(base.with_only_columns(Game.app_id)).all())
    items = db.scalars(
        base.options(selectinload(Game.genres), selectinload(Game.score))
        .order_by(GameScore.index_score.desc(), Game.app_id)
        .limit(limit)
        .offset(offset)
    ).all()
    return Page[GameRead](items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/rating/recalculate",
    status_code=status.HTTP_201_CREATED,
    summary="Пересчитать рейтинг (атомарно)",
    responses={409: {"description": "Пересчёт уже выполняется"}},
)
def run_recalculation(db: DbSession) -> RatingRunRead:
    try:
        run = recalculate(db)
    except RatingInProgressError as exc:
        raise ConflictError(str(exc)) from exc
    return RatingRunRead(id=run.id, status=run.status, games_scored=run.games_scored)


@router.get("/rating/runs", summary="История пересчётов рейтинга")
def rating_runs(db: DbSession, limit: Annotated[int, Query(ge=1, le=100)] = 10) -> list[RatingRunRead]:
    runs = db.scalars(select(RatingRun).order_by(RatingRun.id.desc()).limit(limit)).all()
    return [RatingRunRead(id=r.id, status=r.status, games_scored=r.games_scored) for r in runs]
