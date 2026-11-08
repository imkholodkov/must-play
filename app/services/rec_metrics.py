"""Офлайн-оценка рекомендательной системы.

Четыре метрики:
1. Precision@10 по скрытым тегам — похожие игры ищутся только по жанрам и категориям, а попадание
   проверяется по тегам, которых модель не видела. Слишком частые теги (у 20%+ игр) не считаются.
2. Та же метрика для базовых линий: случайные игры и самые популярные по числу голосов.
3. Качество рекомендованного: средний индекс рекомендованных игр против среднего по рейтингу.
4. Покрытие каталога и разнообразие выдачи (средняя попарная непохожесть рекомендаций).

Пункты 3–4 считаются по рабочей модели (жанры + теги + категории), то есть по тому, что видит пользователь.

Запуск: python -m app.services.rec_metrics   → ml/rec_metrics.json
"""

import json
import logging
import random
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Game
from app.services.recommendations import TOP_K, eligible_quality, game_tokens, rank_similar

logger = logging.getLogger(__name__)

METRICS_FILE = Path(__file__).resolve().parent.parent.parent / "ml" / "rec_metrics.json"
COMMON_TAG_SHARE = 0.2
RANDOM_SEED = 42

Recommender = Callable[[int], list[int]]


def informative_tags(tokens: dict[int, list[str]]) -> dict[int, set[str]]:
    """Теги игры без слишком частых: «Indie» или «Singleplayer» совпадают почти у всех."""
    tags = {a: {t for t in toks if t.startswith("t:")} for a, toks in tokens.items()}
    counts = Counter(t for ts in tags.values() for t in ts)
    common = {t for t, n in counts.items() if n >= COMMON_TAG_SHARE * len(tags)}
    return {a: ts - common for a, ts in tags.items() if ts - common}


def tag_precision(recommend: Recommender, tags: dict[int, set[str]], k: int = TOP_K) -> float:
    """Доля рекомендаций, у которых есть общий информативный тег с исходной игрой."""
    hits = total = 0
    for app_id, own in tags.items():
        for other in recommend(app_id)[:k]:
            total += 1
            hits += bool(own & tags.get(other, set()))
    return round(hits / total, 4) if total else 0.0


def catalog_coverage(recommendations: dict[int, list[int]], catalog: set[int]) -> float:
    """Доля игр каталога, которые хоть раз попали в чьи-то рекомендации."""
    shown = {other for others in recommendations.values() for other in others}
    return round(len(shown & catalog) / len(catalog), 4) if catalog else 0.0


def intra_list_diversity(recommendations: dict[int, list[int]], tokens: dict[int, list[str]]) -> float:
    """Средняя попарная непохожесть (1 − косинус по TF-IDF) игр внутри одной выдачи."""
    ids = sorted({a for others in recommendations.values() for a in others} | set(recommendations))
    ids = [a for a in ids if tokens.get(a)]
    position = {a: i for i, a in enumerate(ids)}
    matrix = TfidfVectorizer(analyzer=lambda doc: doc).fit_transform([tokens[a] for a in ids])
    values = []
    for others in recommendations.values():
        rows = [position[a] for a in others if a in position]
        if len(rows) < 2:
            continue
        sims = (matrix[rows] @ matrix[rows].T).toarray()
        upper = sims[np.triu_indices(len(rows), k=1)]
        values.append(1 - upper.mean())
    return round(float(np.mean(values)), 4) if values else 0.0


def evaluate(session: Session) -> dict:
    quality = eligible_quality(session)
    tokens = game_tokens(session, list(quality))
    tags = informative_tags(tokens)
    rng = random.Random(RANDOM_SEED)
    catalog = [a for a in quality if tokens.get(a)]

    # 1–2. Модель без тегов против базовых линий, проверка по скрытым тегам
    without_tags = {a: [t for t in toks if not t.startswith("t:")] for a, toks in tokens.items()}
    holdout = {a: [o for o, _ in sims] for a, sims in rank_similar(without_tags, quality).items()}
    votes = dict(
        session.execute(select(Game.app_id, Game.positive + Game.negative).where(Game.app_id.in_(catalog))).all()
    )
    popular = sorted(catalog, key=lambda a: votes.get(a, 0), reverse=True)[: TOP_K + 1]
    baselines = {
        "model_without_tags": lambda a: holdout.get(a, []),
        "random": lambda a: [o for o in rng.sample(catalog, min(TOP_K + 1, len(catalog))) if o != a][:TOP_K],
        "popular": lambda a: [o for o in popular if o != a][:TOP_K],
    }
    precision = {name: tag_precision(recommend, tags) for name, recommend in baselines.items()}

    # 3–4. Рабочая модель
    production = {a: [o for o, _ in sims] for a, sims in rank_similar(tokens, quality).items()}
    recommended = [quality[o] for others in production.values() for o in others]
    return {
        "games_evaluated": len(tags),
        "tag_precision_at_10": precision,
        "lift_over_random": round(precision["model_without_tags"] / precision["random"], 1)
        if precision["random"]
        else None,
        "avg_index_recommended": round(float(np.mean(recommended)), 2) if recommended else None,
        "avg_index_catalog": round(float(np.mean([quality[a] for a in catalog])), 2) if catalog else None,
        "catalog_coverage": catalog_coverage(production, set(catalog)),
        "intra_list_diversity": intra_list_diversity(production, tokens),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with SessionLocal() as session:
        metrics = evaluate(session)
    METRICS_FILE.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("Метрики рекомендаций: %s", json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
