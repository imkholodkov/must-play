"""Атомарный пересчёт рейтинга: оценки, история, must play — всё или ничего.

Запуск: python -m app.services.rating
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import CriticReview, Game, GameScore, MustPlayEntry, RatingRun, ScoreHistory
from app.services.scoring import next_must_play_status, score_game

logger = logging.getLogger(__name__)
BATCH_SIZE = 5000


class RatingInProgressError(Exception):
    """Другой пересчёт ещё идёт — второй запускать нельзя (API ответит 409)."""


def _chunks(rows: list[dict]):
    for start in range(0, len(rows), BATCH_SIZE):
        yield rows[start : start + BATCH_SIZE]


def recalculate(session: Session) -> RatingRun:
    """Пересчитать рейтинг всех игр в одной транзакции и вернуть запись о запуске."""
    if session.scalar(select(RatingRun.id).where(RatingRun.status == "running").with_for_update()):
        raise RatingInProgressError("пересчёт рейтинга уже выполняется")
    run = RatingRun(status="running")
    session.add(run)
    session.commit()

    try:
        critic = dict(
            (app_id, (avg, cnt))
            for app_id, avg, cnt in session.execute(
                select(CriticReview.app_id, func.avg(CriticReview.score), func.count(CriticReview.score))
                .where(CriticReview.score.is_not(None))
                .group_by(CriticReview.app_id)
            )
        )
        statuses = dict(session.execute(select(MustPlayEntry.app_id, MustPlayEntry.status)).tuples().all())

        scores, history, must_play = [], [], []
        for app_id, positive, negative in session.execute(select(Game.app_id, Game.positive, Game.negative)):
            avg, cnt = critic.get(app_id, (None, 0))
            s = score_game(positive, negative, float(avg) if avg is not None else None, cnt)
            scores.append(
                {
                    "app_id": app_id,
                    "run_id": run.id,
                    "player_score": s.player_score,
                    "critic_score": s.critic_score,
                    "critic_reviews_count": cnt,
                    "index_score": s.index_score,
                    "is_eligible": s.is_eligible,
                    "divergence": s.divergence,
                }
            )
            if s.is_eligible and s.index_score is not None:
                history.append({"run_id": run.id, "app_id": app_id, "index_score": s.index_score})
            current = statuses.get(app_id)
            new = next_must_play_status(current, s.index_score, s.is_eligible)
            if new is not None and new != current:
                must_play.append({"app_id": app_id, "status": new, "run_id": run.id})

        for rows in _chunks(scores):
            stmt = insert(GameScore).values(rows)
            cols = {c: stmt.excluded[c] for c in rows[0] if c != "app_id"}
            session.execute(stmt.on_conflict_do_update(index_elements=["app_id"], set_=cols))
        for rows in _chunks(history):
            session.execute(insert(ScoreHistory), rows)
        for rows in _chunks(must_play):
            stmt = insert(MustPlayEntry).values(rows)
            session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["app_id"],
                    set_={"status": stmt.excluded.status, "run_id": stmt.excluded.run_id, "changed_at": func.now()},
                )
            )

        run.games_scored = len(scores)
        run.status = "success"
        run.finished_at = datetime.now(UTC)
        session.commit()
    except BaseException:
        session.rollback()
        run = session.merge(run)
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        session.commit()
        raise
    return run


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with SessionLocal() as session:
        run = recalculate(session)
    logger.info("Пересчёт рейтинга #%s %s: игр %s", run.id, run.status, run.games_scored)


if __name__ == "__main__":
    main()
