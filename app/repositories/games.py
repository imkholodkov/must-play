"""Доступ к играм в БД: выборка с фильтрами, сортировкой и пагинацией, CRUD."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import CriticReview, Game, GameScore, Genre, MustPlayEntry, Outlet


class SortField(StrEnum):
    index = "index"
    name = "name"
    release_date = "release_date"
    votes = "votes"
    price = "price"


SORT_COLUMNS = {
    SortField.index: GameScore.index_score,
    SortField.name: Game.name,
    SortField.release_date: Game.release_date,
    SortField.votes: Game.positive + Game.negative,
    SortField.price: Game.price,
}


@dataclass
class GameFilters:
    q: str | None = None
    genre: str | None = None
    platform: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    max_price: Decimal | None = None
    free: bool | None = None
    eligible: bool | None = None
    divergence: str | None = None


def _apply_filters(stmt: Select, f: GameFilters) -> Select:
    if f.q:
        stmt = stmt.where(Game.name.ilike(f"%{f.q}%"))
    if f.genre:
        stmt = stmt.where(Game.genres.any(func.lower(Genre.name) == f.genre.lower()))
    if f.platform:
        stmt = stmt.where(getattr(Game, f.platform).is_(True))
    if f.year_from:
        stmt = stmt.where(func.extract("year", Game.release_date) >= f.year_from)
    if f.year_to:
        stmt = stmt.where(func.extract("year", Game.release_date) <= f.year_to)
    if f.max_price is not None:
        stmt = stmt.where(Game.price <= f.max_price)
    if f.free is not None:
        stmt = stmt.where(Game.is_free.is_(f.free))
    if f.eligible is not None:
        stmt = stmt.where(GameScore.is_eligible.is_(f.eligible))
    if f.divergence:
        stmt = stmt.where(GameScore.divergence == f.divergence)
    return stmt


def list_games(
    session: Session, filters: GameFilters, sort: SortField, desc: bool, limit: int, offset: int
) -> tuple[list[Game], int]:
    base = _apply_filters(select(Game).outerjoin(GameScore, GameScore.app_id == Game.app_id), filters)
    total = session.scalar(select(func.count()).select_from(base.subquery()))
    column = SORT_COLUMNS[sort]
    order = column.desc().nulls_last() if desc else column.asc().nulls_last()
    items = session.scalars(
        base.options(selectinload(Game.genres), selectinload(Game.score))
        .order_by(order, Game.app_id)
        .limit(limit)
        .offset(offset)
    ).all()
    return list(items), total


def get_game(session: Session, app_id: int) -> Game | None:
    return session.get(Game, app_id)


def get_reviews(session: Session, app_id: int) -> list[dict]:
    rows = session.execute(
        select(Outlet.name, CriticReview.quote, CriticReview.raw_score, CriticReview.score)
        .outerjoin(Outlet, Outlet.id == CriticReview.outlet_id)
        .where(CriticReview.app_id == app_id)
        .order_by(CriticReview.score.desc().nulls_last())
    )
    return [{"outlet": o, "quote": q, "raw_score": r, "score": s} for o, q, r, s in rows]


def get_must_play_status(session: Session, app_id: int) -> str | None:
    return session.scalar(select(MustPlayEntry.status).where(MustPlayEntry.app_id == app_id))


def genres_by_names(session: Session, names: list[str]) -> list[Genre]:
    """Найти жанры по именам, недостающие создать."""
    existing = {g.name.lower(): g for g in session.scalars(select(Genre).where(Genre.name.in_(names)))}
    result = []
    for name in dict.fromkeys(n.strip() for n in names if n.strip()):
        genre = existing.get(name.lower())
        if genre is None:
            genre = Genre(name=name)
            session.add(genre)
            existing[name.lower()] = genre
        result.append(genre)
    return result
