"""ETL обзоров прессы: разбор цитат → издания → critic_reviews → отчёт etl_runs.

Запуск после импорта каталога: python -m app.etl.import_reviews --source data/steam_games_reviews.csv
Файл маленький (около 5 МБ), поэтому читается целиком: так для каждого издания
выбирается самое частое написание названия.
"""

import argparse
import csv
import logging
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.etl.cleaning import parse_int
from app.etl.reviews import ParsedQuote, outlet_key, parse_reviews
from app.models import CriticReview, EtlRun, Game, Outlet

logger = logging.getLogger(__name__)
BATCH_SIZE = 1000


def read_reviews(path: Path, reasons: Counter[str]) -> dict[int, list[ParsedQuote]]:
    """Прочитать файл и разобрать цитаты. Непригодные строки считаются в reasons."""
    result: dict[int, list[ParsedQuote]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            app_id = parse_int(row.get("app_id"))
            quotes = parse_reviews(row.get("reviews"))
            if app_id is None:
                reasons["bad_app_id"] += 1
            elif app_id in result:
                reasons["duplicate_app_id"] += 1
            elif not quotes:
                reasons["no_quotes"] += 1
            else:
                result[app_id] = quotes
    return result


def ensure_outlets(session: Session, by_game: dict[int, list[ParsedQuote]]) -> dict[str, int]:
    """Создать издания и вернуть ключ → id. Имя издания — самое частое написание."""
    spellings: dict[str, Counter[str]] = defaultdict(Counter)
    for quotes in by_game.values():
        for q in quotes:
            if q.outlet and outlet_key(q.outlet):
                spellings[outlet_key(q.outlet)][q.outlet[:200]] += 1
    rows = [{"normalized_name": key[:200], "name": names.most_common(1)[0][0]} for key, names in spellings.items()]
    for start in range(0, len(rows), BATCH_SIZE):
        stmt = insert(Outlet).values(rows[start : start + BATCH_SIZE])
        session.execute(
            stmt.on_conflict_do_update(index_elements=["normalized_name"], set_={"name": stmt.excluded.name})
        )
    return {key: id_ for key, id_ in session.execute(select(Outlet.normalized_name, Outlet.id))}


def review_rows(app_id: int, quotes: list[ParsedQuote], outlet_ids: dict[str, int]) -> list[dict]:
    """Строки critic_reviews одной игры: одно издание — один обзор (первый в тексте)."""
    rows, seen = [], set()
    for q in quotes:
        outlet_id = outlet_ids.get(outlet_key(q.outlet)[:200]) if q.outlet else None
        if outlet_id is not None and outlet_id in seen:
            continue
        seen.add(outlet_id)
        rows.append(
            {
                "app_id": app_id,
                "outlet_id": outlet_id,
                "quote": q.quote,
                "raw_score": (q.raw_score or "")[:20] or None,
                "score": q.score,
            }
        )
    return rows


def run_import(session: Session, source: Path) -> EtlRun:
    run = EtlRun(source=str(source), status="running", rejection_reasons={})
    session.add(run)
    session.commit()
    reasons: Counter[str] = Counter()
    try:
        by_game = read_reviews(source, reasons)
        run.rows_read = len(by_game) + sum(reasons.values())
        known = set(session.scalars(select(Game.app_id).where(Game.app_id.in_(list(by_game)))))
        for app_id in by_game.keys() - known:
            reasons["unknown_game"] += 1
            del by_game[app_id]

        outlet_ids = ensure_outlets(session, by_game)
        already = set(session.scalars(select(CriticReview.app_id).distinct()))
        app_ids = list(by_game)
        for start in range(0, len(app_ids), BATCH_SIZE):
            chunk = app_ids[start : start + BATCH_SIZE]
            # Обзоры игры перезаписываются целиком: повторный запуск не плодит дубли
            session.execute(delete(CriticReview).where(CriticReview.app_id.in_(chunk)))
            rows = [row for app_id in chunk for row in review_rows(app_id, by_game[app_id], outlet_ids)]
            session.execute(insert(CriticReview), rows)
        run.rows_updated = len(already & set(app_ids))
        run.rows_loaded = len(app_ids) - run.rows_updated
        run.status = "success"
    except BaseException:
        session.rollback()
        run = session.merge(run)
        run.status = "failed"
        raise
    finally:
        run.rows_rejected = sum(reasons.values())
        run.rejection_reasons = dict(reasons)
        run.finished_at = datetime.now(UTC)
        session.commit()
    return run


def main() -> None:
    parser = argparse.ArgumentParser(description="Импорт обзоров прессы в БД")
    parser.add_argument("--source", type=Path, default=Path("data/steam_games_reviews.csv"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not args.source.exists():
        parser.error(f"нет файла {args.source}: скачайте данные командой python -m app.etl.download_data")

    with SessionLocal() as session:
        run = run_import(session, args.source)
    logger.info(
        "Обзоры %s: игр прочитано %s, новых %s, обновлено %s, отклонено %s %s",
        run.status,
        run.rows_read,
        run.rows_loaded,
        run.rows_updated,
        run.rows_rejected,
        run.rejection_reasons,
    )


if __name__ == "__main__":
    main()
