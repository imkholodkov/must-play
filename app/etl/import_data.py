"""ETL каталога игр: извлечение → проверка → очистка → загрузка → отчёт.

Запуск: python -m app.etl.import_data --source data/steam_games.csv [--batch-size 1000]
"""

import argparse
import csv
import logging
import sys
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.etl.load import Loader
from app.etl.transform import GameRecord, RejectedRow, transform_row
from app.models import EtlRun

logger = logging.getLogger(__name__)

# Описания игр бывают длиннее стандартного лимита поля в модуле csv
csv.field_size_limit(sys.maxsize)


def read_rows(path: Path) -> Iterator[dict[str, str]]:
    """Читать CSV построчно: файл на 925 МБ целиком в память не грузится."""
    with path.open(encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def run_import(session: Session, source: Path, batch_size: int = 1000) -> EtlRun:
    """Импортировать каталог в одной транзакции и записать отчёт в etl_runs."""
    run = EtlRun(source=str(source), status="running", rejection_reasons={})
    session.add(run)
    session.commit()

    reasons: Counter[str] = Counter()
    seen: set[int] = set()
    batch: list[GameRecord] = []
    loader = Loader(session)

    def flush() -> None:
        loaded, updated = loader.load_batch(batch)
        run.rows_loaded += loaded
        run.rows_updated += updated
        batch.clear()

    try:
        for row in read_rows(source):
            run.rows_read += 1
            try:
                record = transform_row(row)
                if record.game["app_id"] in seen:
                    raise RejectedRow("duplicate_app_id")
            except RejectedRow as exc:
                reasons[exc.reason] += 1
                continue
            seen.add(record.game["app_id"])
            batch.append(record)
            if len(batch) >= batch_size:
                flush()
                logger.info("Обработано строк: %s", run.rows_read)
        if batch:
            flush()
        run.status = "success"
    except BaseException:
        # BaseException: прерывание по Ctrl+C тоже должно пометить запуск как failed, а не оставить running
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
    parser = argparse.ArgumentParser(description="Импорт каталога игр Steam в БД")
    parser.add_argument("--source", type=Path, default=Path("data/steam_games.csv"))
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not args.source.exists():
        parser.error(f"нет файла {args.source}: скачайте данные командой python -m app.etl.download_data")

    with SessionLocal() as session:
        run = run_import(session, args.source, args.batch_size)
    logger.info(
        "ETL %s: прочитано %s, новых %s, обновлено %s, отклонено %s %s",
        run.status,
        run.rows_read,
        run.rows_loaded,
        run.rows_updated,
        run.rows_rejected,
        run.rejection_reasons,
    )


if __name__ == "__main__":
    main()
