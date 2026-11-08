"""Наполнение БД тестовыми данными из выборки data/sample — без полного датасета.

Запуск: python -m app.seed

Цепочка та же, что на полных данных: каталог → обзоры прессы → два пересчёта рейтинга
(во втором кандидаты попадают в must play) → похожие игры. Повторный запуск дублей не создаёт.
"""

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.etl import import_data, import_reviews
from app.services import rating, recommendations

logger = logging.getLogger(__name__)

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"
GAMES_SAMPLE = SAMPLE_DIR / "steam_games_sample.csv"
REVIEWS_SAMPLE = SAMPLE_DIR / "steam_games_reviews_sample.csv"


def seed(session: Session, games: Path = GAMES_SAMPLE, reviews: Path = REVIEWS_SAMPLE) -> dict:
    catalog = import_data.run_import(session, games)
    press = import_reviews.run_import(session, reviews)
    rating.recalculate(session)
    # второй пересчёт нужен, чтобы кандидаты успели перейти в must play
    last_run = rating.recalculate(session)
    similar = recommendations.build_similarities(session)
    return {
        "games_loaded": catalog.rows_loaded + catalog.rows_updated,
        "games_rejected": catalog.rows_rejected,
        "games_with_reviews": press.rows_loaded + press.rows_updated,
        "games_scored": last_run.games_scored,
        "similar_pairs": similar["pairs"],
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with SessionLocal() as session:
        result = seed(session)
    logger.info("Seed готов: %s", result)


if __name__ == "__main__":
    main()
