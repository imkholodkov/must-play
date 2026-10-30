"""Рекомендательная система (content-based).

1. Похожие игры: вектор игры — TF-IDF по жанрам, тегам и категориям; близость — косинусная.
   Итоговый ранг смешивает близость и индекс качества, чтобы похожие, но слабые игры не выходили наверх.
2. Подбор по анкете: фильтры по жанрам, тегам, режиму, платформе, языку и цене, сортировка по индексу.

Похожие игры считаются офлайн после пересчёта рейтинга: python -m app.services.recommendations
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.core.database import SessionLocal
from app.models import Category, Game, GameScore, GameSimilarity, Genre, Language, Tag
from app.models.catalog import game_categories, game_genres, game_tags

logger = logging.getLogger(__name__)

TOP_K = 10
CANDIDATES = 30  # соседей по сходству до пересортировки с учётом качества
SIMILARITY_WEIGHT = 0.8
QUALITY_WEIGHT = 0.2
MODES = {
    "single": {"Single-player"},
    "coop": {"Co-op", "Online Co-op", "LAN Co-op", "Shared/Split Screen Co-op"},
    "multiplayer": {"Multi-player", "Online PvP", "PvP", "LAN PvP", "Cross-Platform Multiplayer"},
}


def _features(session: Session, app_ids: list[int]) -> dict[int, list[str]]:
    """Признаки игры как список токенов: g:Action, t:Roguelike, c:Co-op."""
    tokens: dict[int, list[str]] = defaultdict(list)
    for prefix, link, model, column in (
        ("g", game_genres, Genre, game_genres.c.genre_id),
        ("t", game_tags, Tag, game_tags.c.tag_id),
        ("c", game_categories, Category, game_categories.c.category_id),
    ):
        rows = session.execute(
            select(link.c.app_id, model.name).join(model, model.id == column).where(link.c.app_id.in_(app_ids))
        )
        for app_id, name in rows:
            tokens[app_id].append(f"{prefix}:{name}")
    return tokens


def build_similarities(session: Session, top_k: int = TOP_K) -> dict:
    """Пересчитать таблицу game_similarities для допущенных игр в одной транзакции."""
    games = dict(
        session.execute(
            select(GameScore.app_id, GameScore.index_score).where(
                GameScore.is_eligible, GameScore.index_score.is_not(None)
            )
        ).all()
    )
    tokens = _features(session, list(games))
    app_ids = [a for a in games if tokens.get(a)]
    if len(app_ids) < 2:
        return {"games": 0, "pairs": 0, "genre_precision": None}

    vectorizer = TfidfVectorizer(analyzer=lambda doc: doc)  # документ уже разбит на токены
    matrix = vectorizer.fit_transform([tokens[a] for a in app_ids])
    neighbours = NearestNeighbors(n_neighbors=min(CANDIDATES + 1, len(app_ids)), metric="cosine").fit(matrix)
    distances, indices = neighbours.kneighbors(matrix)

    rows, hits, total = [], 0, 0
    for row, app_id in enumerate(app_ids):
        genres = {t for t in tokens[app_id] if t.startswith("g:")}
        scored = []
        for dist, idx in zip(distances[row], indices[row], strict=True):
            other = app_ids[idx]
            if other == app_id:
                continue
            similarity = 1 - dist
            rank_score = SIMILARITY_WEIGHT * similarity + QUALITY_WEIGHT * games[other] / 100
            scored.append((rank_score, other, similarity))
        scored.sort(reverse=True)
        for rank, (_, other, similarity) in enumerate(scored[:top_k], start=1):
            rows.append({"app_id": app_id, "similar_app_id": other, "rank": rank, "score": round(similarity, 4)})
            total += 1
            hits += bool(genres & {t for t in tokens[other] if t.startswith("g:")})

    session.execute(delete(GameSimilarity))
    for start in range(0, len(rows), 10000):
        session.execute(insert(GameSimilarity), rows[start : start + 10000])
    session.commit()
    # Доля рекомендаций, у которых есть общий жанр с исходной игрой (precision@K по жанру)
    return {"games": len(app_ids), "pairs": len(rows), "genre_precision": round(hits / total, 3)}


def similar_games(session: Session, app_id: int, limit: int) -> list[tuple[Game, float]]:
    rows = session.execute(
        select(Game, GameSimilarity.score)
        .join(GameSimilarity, GameSimilarity.similar_app_id == Game.app_id)
        .where(GameSimilarity.app_id == app_id)
        .options(selectinload(Game.genres), selectinload(Game.score))
        .order_by(GameSimilarity.rank)
        .limit(limit)
    )
    return [(game, score) for game, score in rows]


@dataclass
class Preferences:
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    mode: str | None = None
    platform: str | None = None
    language: str | None = None
    max_price: Decimal | None = None
    exclude: list[int] = field(default_factory=list)


def recommend(session: Session, prefs: Preferences, limit: int) -> list[Game]:
    """Подбор по анкете: допущенные игры, подходящие под все условия, по убыванию индекса."""
    stmt = select(Game).join(GameScore, GameScore.app_id == Game.app_id).where(GameScore.is_eligible)
    for name in prefs.genres:
        stmt = stmt.where(Game.genres.any(func.lower(Genre.name) == name.lower()))
    for name in prefs.tags:
        stmt = stmt.where(Game.tags.any(func.lower(Tag.name) == name.lower()))
    if prefs.mode:
        stmt = stmt.where(Game.categories.any(Category.name.in_(MODES[prefs.mode])))
    if prefs.platform:
        stmt = stmt.where(getattr(Game, prefs.platform).is_(True))
    if prefs.language:
        stmt = stmt.where(Game.languages.any(func.lower(Language.name) == prefs.language.lower()))
    if prefs.max_price is not None:
        stmt = stmt.where((Game.price <= prefs.max_price) | Game.is_free)
    if prefs.exclude:
        stmt = stmt.where(Game.app_id.not_in(prefs.exclude))
    stmt = stmt.options(selectinload(Game.genres), selectinload(Game.score))
    return list(session.scalars(stmt.order_by(GameScore.index_score.desc(), Game.app_id).limit(limit)))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with SessionLocal() as session:
        stats = build_similarities(session)
    logger.info("Похожие игры: %s", stats)


if __name__ == "__main__":
    main()
