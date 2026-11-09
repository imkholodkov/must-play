# Шпаргалка: команды

Все команды запускаются из корня проекта. В Docker перед модулем пишется `docker compose exec app`, локально — без этого префикса, но с активированным `.venv`.

## Запуск в Docker

| Команда | Что делает |
|---|---|
| `cp .env.example .env` | создаёт файл настроек из примера (один раз) |
| `docker compose up --build -d` | собирает образ и поднимает db, app, scheduler; миграции применяются при старте |
| `docker compose up -d` | поднимает без пересборки (если код не менялся) |
| `docker compose ps` | какие контейнеры запущены |
| `docker compose logs -f app` | логи приложения в реальном времени |
| `docker compose down` | останавливает контейнеры, данные в томе сохраняются |
| `docker compose down -v` | останавливает и **удаляет базу** (том pgdata) |

После запуска: интерфейс http://localhost:8000/ui, Swagger http://localhost:8000/docs.

## Наполнение данными

| Команда | Что делает |
|---|---|
| `docker compose exec app python -m app.seed` | быстрые тестовые данные из `data/sample/` — всё сразу, без скачивания |
| `docker compose exec app python -m app.etl.download_data` | скачивает датасет с Google Drive в `data/` (ZIP 179 МБ → CSV 925 МБ); `--only` — один файл |
| `docker compose exec app python -m app.etl.import_data` | чистит и загружает каталог игр (~2 мин); `--source`, `--batch-size` |
| `docker compose exec app python -m app.etl.import_reviews` | чистит и загружает обзоры прессы; `--source` |
| `docker compose exec app python -m app.services.rating` | пересчитывает рейтинг и статусы must play |
| `docker compose exec app python -m app.services.recommendations` | строит таблицу похожих игр (~45 с) |

Порядок полного наполнения: download_data → import_data → import_reviews → rating → recommendations.
Must play требует двух пересчётов подряд: после первого игры только кандидаты.

## ML и аналитика (локально)

| Команда | Что делает |
|---|---|
| `python -m ml.train` | обучает модели hit и press, пишет `models/*.pkl` и `ml/metrics.json` (ROC-AUC) |
| `python -m app.services.rec_metrics` | считает качество рекомендаций (Precision@10), пишет `ml/rec_metrics.json` |
| `python ml/notebooks/make_eda.py` | пересобирает ноутбук `ml/notebooks/eda.ipynb` |

## Локальная разработка без Docker-приложения

| Команда | Что делает |
|---|---|
| `docker compose up -d db` | поднимает только PostgreSQL |
| `python -m venv .venv && source .venv/bin/activate` | создаёт и активирует виртуальное окружение |
| `pip install -r requirements-dev.txt` | ставит зависимости вместе с тестовыми |
| `alembic upgrade head` | применяет миграции к БД |
| `uvicorn app.main:app --reload` | запускает API с перезапуском при правке кода |

## Проверки

| Команда | Что делает |
|---|---|
| `ruff check . && ruff format --check .` | линтер и проверка форматирования (как в CI) |
| `ruff format .` | автоматически форматирует код |
| `docker compose exec db psql -U mustplay -c "create database mustplay_test"` | создаёт отдельную базу для тестов (один раз) |
| `pytest` | все тесты с покрытием (порог 70%) |
| `pytest tests/unit` | только быстрые тесты без БД |
| `pytest --alluredir allure-results` | тесты с отчётом Allure (в CI он публикуется на GitHub Pages) |

## Запросы к API (curl)

| Команда | Что делает |
|---|---|
| `curl "http://localhost:8000/health"` | сервис и БД живы |
| `curl "http://localhost:8000/rating?genre=RPG&decade=2010&limit=3"` | рейтинг с фильтрами |
| `curl "http://localhost:8000/must-play"` | список must play |
| `curl "http://localhost:8000/games?q=knight&sort=release_date&limit=5"` | поиск игр |
| `curl "http://localhost:8000/games/504230"` | карточка игры |
| `curl "http://localhost:8000/games/504230/similar"` | похожие игры |
| `curl -X POST http://localhost:8000/rating/recalculate` | пересчёт рейтинга через API |
| `curl "http://localhost:8000/analytics/divergence?kind=overrated&limit=5"` | игры, которые пресса переоценила |
| `curl -X POST http://localhost:8000/ml/predict-from-csv -F model=hit -F file=@games.csv` | прогноз модели по CSV |
