"""Аналитические запросы: группировки, средние, топ-N, динамика по годам."""

from sqlalchemy import Float, Integer, case, cast, func, select
from sqlalchemy.orm import Session

from app.models import CriticReview, Game, GameScore, Genre, Outlet
from app.models.catalog import game_genres

YEAR = cast(func.extract("year", Game.release_date), Integer)


def genres_summary(session: Session, min_games: int) -> list[dict]:
    """По жанрам: число допущенных игр, средний индекс, средняя доля положительных, доля бесплатных."""
    share = cast(Game.positive, Float) * 100 / (Game.positive + Game.negative)
    rows = session.execute(
        select(
            Genre.name,
            func.count().label("games"),
            func.avg(GameScore.index_score),
            func.avg(share),
            func.avg(case((Game.is_free, 100.0), else_=0.0)),
        )
        .join(game_genres, game_genres.c.genre_id == Genre.id)
        .join(Game, Game.app_id == game_genres.c.app_id)
        .join(GameScore, GameScore.app_id == Game.app_id)
        .where(GameScore.is_eligible)
        .group_by(Genre.name)
        .having(func.count() >= min_games)
        .order_by(func.avg(GameScore.index_score).desc())
    )
    return [
        {"genre": g, "games": n, "avg_index": round(i, 1), "avg_positive_share": round(s, 1), "free_share": round(f, 1)}
        for g, n, i, s, f in rows
    ]


def releases_by_year(session: Session, year_from: int, year_to: int) -> list[dict]:
    """Динамика по годам: релизы, доля бесплатных, средняя цена платных, средний индекс допущенных."""
    rows = session.execute(
        select(
            YEAR,
            func.count(),
            func.avg(case((Game.is_free, 100.0), else_=0.0)),
            func.avg(case((Game.is_free.is_(False), Game.price))),
            func.avg(case((GameScore.is_eligible, GameScore.index_score))),
        )
        .outerjoin(GameScore, GameScore.app_id == Game.app_id)
        .where(YEAR.between(year_from, year_to))
        .group_by(YEAR)
        .order_by(YEAR)
    )
    return [
        {
            "year": y,
            "releases": n,
            "free_share": round(f, 1),
            "avg_price": round(float(p), 2) if p is not None else None,
            "avg_index": round(i, 1) if i is not None else None,
        }
        for y, n, f, p, i in rows
    ]


def divergence_top(session: Session, kind: str, limit: int) -> list[dict]:
    """Топ игр, где пресса сильнее всего расходится с игроками."""
    share = cast(Game.positive, Float) * 100 / (Game.positive + Game.negative)
    gap = GameScore.critic_score - share
    rows = session.execute(
        select(Game.app_id, Game.name, GameScore.critic_score, share, gap)
        .join(GameScore, GameScore.app_id == Game.app_id)
        .where(GameScore.divergence == kind)
        .order_by(gap.desc() if kind == "overrated" else gap.asc())
        .limit(limit)
    )
    return [
        {"app_id": a, "name": n, "critic_score": c, "positive_share": round(s, 1), "gap": round(g, 1)}
        for a, n, c, s, g in rows
    ]


def outlets_strictness(session: Session, min_reviews: int, limit: int, strict: bool) -> list[dict]:
    """Строгость изданий: средняя оценка издания минус средняя оценка всех изданий."""
    overall = session.scalar(select(func.avg(CriticReview.score)))
    if overall is None:
        return []
    avg = func.avg(CriticReview.score)
    rows = session.execute(
        select(Outlet.name, func.count(CriticReview.score), avg)
        .join(CriticReview, CriticReview.outlet_id == Outlet.id)
        .where(CriticReview.score.is_not(None))
        .group_by(Outlet.name)
        .having(func.count(CriticReview.score) >= min_reviews)
        .order_by(avg.asc() if strict else avg.desc())
        .limit(limit)
    )
    return [
        {"outlet": o, "reviews": n, "avg_score": round(float(a), 1), "vs_average": round(float(a - overall), 1)}
        for o, n, a in rows
    ]
