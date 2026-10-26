"""Скачивание датасета Steam с Google Drive.

Запуск: python -m app.etl.download_data [--only games|reviews] [--force]
"""

import argparse
import logging
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DRIVE_URL = "https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
CHUNK_SIZE = 1024 * 1024

# Имя итогового CSV -> (переменная окружения с ID файла на Drive, ID по умолчанию, архив ли это)
SOURCES = {
    "games": ("steam_games.csv", "STEAM_GAMES_DRIVE_ID", "16Voa_31N5cg1n_REv9KKJXPBvKyAAPOJ", False),
    "reviews": ("steam_games_reviews.csv", "STEAM_REVIEWS_DRIVE_ID", "1EAemIGRXGZg6F-_reWqqY7RtkWdzGGcR", True),
}


def download(file_id: str, target: Path) -> None:
    """Скачать файл с Google Drive потоково, без загрузки в память целиком."""
    url = DRIVE_URL.format(file_id=file_id)
    tmp = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url) as response, tmp.open("wb") as out:
        if "text/html" in response.headers.get("Content-Type", ""):
            raise RuntimeError(f"Drive вернул HTML вместо файла: проверьте доступ по ссылке для {file_id}")
        shutil.copyfileobj(response, out, CHUNK_SIZE)
    tmp.replace(target)


def fetch(name: str, force: bool = False) -> Path:
    """Скачать один источник в data/ и при необходимости распаковать архив."""
    csv_name, env_var, default_id, is_zip = SOURCES[name]
    target = DATA_DIR / csv_name
    if target.exists() and not force:
        logger.info("%s уже есть, пропускаю", target)
        return target

    DATA_DIR.mkdir(exist_ok=True)
    file_id = os.getenv(env_var, default_id)
    if not is_zip:
        logger.info("Скачиваю %s", csv_name)
        download(file_id, target)
        return target

    archive = DATA_DIR / f"{csv_name}.zip"
    logger.info("Скачиваю архив %s", archive.name)
    download(file_id, archive)
    with zipfile.ZipFile(archive) as zf:
        zf.extract(csv_name, DATA_DIR)
    archive.unlink()
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Скачать датасет Steam в data/")
    parser.add_argument("--only", choices=SOURCES, help="скачать только один файл")
    parser.add_argument("--force", action="store_true", help="перекачать, даже если файл уже есть")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for name in [args.only] if args.only else SOURCES:
        path = fetch(name, force=args.force)
        logger.info("Готово: %s (%.1f МБ)", path, path.stat().st_size / 1024 / 1024)


if __name__ == "__main__":
    main()
