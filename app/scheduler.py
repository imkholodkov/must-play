"""Плановый пересчёт рейтинга и похожих игр по расписанию (APScheduler).

Запуск: python -m app.scheduler
Расписание — cron-строка в переменной RATING_CRON, по умолчанию каждый понедельник в 03:00 UTC.
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services import rating, recommendations

logger = logging.getLogger(__name__)


def refresh() -> dict | None:
    """Пересчитать рейтинг и похожие игры. Если пересчёт уже идёт, пропустить запуск."""
    with SessionLocal() as session:
        try:
            run = rating.recalculate(session)
        except rating.RatingInProgressError:
            logger.warning("Пересчёт рейтинга уже идёт, плановый запуск пропущен")
            return None
        similar = recommendations.build_similarities(session)
    result = {"rating_run": run.id, "games_scored": run.games_scored, "similar_pairs": similar["pairs"]}
    logger.info("Плановое обновление: %s", result)
    return result


def build_scheduler(cron: str) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="UTC")
    # max_instances=1: если пересчёт затянулся, следующий запуск на него не наложится
    scheduler.add_job(refresh, CronTrigger.from_crontab(cron, timezone="UTC"), id="refresh", max_instances=1)
    return scheduler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cron = get_settings().rating_cron
    logger.info("Плановый пересчёт рейтинга по расписанию «%s» (UTC)", cron)
    build_scheduler(cron).start()


if __name__ == "__main__":
    main()
