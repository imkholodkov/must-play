# Шпаргалка: где что лежит

## Быстрый поиск по вопросу

| Спросят про… | Смотреть |
|---|---|
| Точку входа приложения, подключение роутеров | `app/main.py` |
| Настройки, переменные окружения | `app/core/config.py`, `.env.example` |
| Подключение к БД, сессии | `app/core/database.py` |
| Ошибки валидации на русском | `app/core/errors.py` |
| Таблицы БД (ORM-модели) | `app/models/` — `game.py`, `catalog.py`, `rating.py`, `review.py`, `etl.py` |
| Схему БД картинкой | `docs/erd.md` |
| Миграции | `migrations/versions/132a2c8a1a83_initial_schema.py`, `alembic.ini` |
| Pydantic-схемы запросов и ответов | `app/schemas/` |
| SQL-запросы к БД | `app/repositories/` — `games.py`, `analytics.py` |
| Эндпоинты | `app/api/` (таблица ниже) |
| **Очистку и унификацию данных (задача минимум)** | `app/etl/cleaning.py` — владельцы, жанры, языки, HTML-сущности |
| Приведение оценок прессы к 0–100, издания | `app/etl/reviews.py` |
| Превращение строки CSV в записи | `app/etl/transform.py` |
| Загрузку в БД (upsert, без дублей) | `app/etl/load.py` |
| Запуск импорта каталога / обзоров | `app/etl/import_data.py`, `app/etl/import_reviews.py` |
| Скачивание датасета с Google Drive | `app/etl/download_data.py` |
| Отчёт об импорте и отклонённые строки | таблица `etl_runs`, модель `app/models/etl.py` |
| **Формулу рейтинга** (байес, пресса, флаг расхождения, must play) | `app/services/scoring.py` — чистые функции, все пороги константами вверху |
| Пересчёт рейтинга в БД (атомарно, всё или ничего) | `app/services/rating.py` |
| Расписание пересчёта | `app/scheduler.py` (cron из `RATING_CRON`) |
| **Рекомендательную систему** | `app/services/recommendations.py` — TF-IDF по жанрам/тегам + ближайшие соседи |
| Метрики качества рекомендаций (Precision@10) | `app/services/rec_metrics.py`, результат `ml/rec_metrics.json` |
| **ML: обучение моделей, ROC-AUC** | `ml/train.py`, результат `ml/metrics.json`, модели `models/*.pkl` |
| Признаки для ML | `app/ml/features.py` |
| Загрузка/хранение модели в API | `app/ml/registry.py` |
| EDA, графики | `ml/notebooks/eda.ipynb` (собирается `ml/notebooks/make_eda.py`) |
| Тестовые данные (seed) | `app/seed.py`, `data/sample/` |
| Веб-интерфейс `/ui` | `frontend/` — `index.html`, `app.js`, `style.css` |
| Тесты | `tests/unit/` (без БД), `tests/integration/` (с БД), фикстуры `tests/conftest.py` |
| CI: линтер, тесты, покрытие, Allure | `.github/workflows/ci.yml`; отчёты https://imkholodkov.github.io/must-play/ |
| Docker | `Dockerfile`, `docker-compose.yml` (сервисы db, app, scheduler) |
| Зависимости, настройки ruff/pytest | `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` |
| Текст задания | `docs/assignment.md` |
| Как запустить | `README.md` |
| Презентации | `docs/presentation/idea.html`, `defense.html` (собираются `build.py`) |

## Эндпоинты

| Файл | Методы |
|---|---|
| `app/api/health.py` | `GET /health` |
| `app/api/games.py` | `GET /games`, `GET /games/{app_id}`, `POST /games`, `DELETE /games/{app_id}` |
| `app/api/genres.py` | `GET /genres`, `POST /genres` |
| `app/api/rating.py` | `GET /rating`, `GET /must-play`, `POST` пересчёт, `GET /rating/runs` |
| `app/api/recommendations.py` | `GET /games/{app_id}/similar`, `POST /recommendations` |
| `app/api/analytics.py` | `GET /analytics/genres`, `/releases`, `/divergence`, `/outlets` |
| `app/api/ml.py` | `POST /ml/upload-model`, `/ml/predict`, `/ml/predict-from-csv` |

Документация Swagger: `http://localhost:8000/docs`.

## Слои (как идёт запрос)

`app/api` (роутер) → `app/services` (бизнес-логика) → `app/repositories` (SQL) → `app/models` (таблицы).
Данные: CSV → `app/etl` (чистка, разбор) → PostgreSQL → `app/services/rating.py` → оценки и must play.

## Таблицы БД

Каталог: `games`, `genres`, `tags`, `categories`, `languages`, `developers` (+ связующие).
Пресса: `outlets`, `critic_reviews`.
Рейтинг: `rating_runs`, `game_scores`, `score_history`, `must_play_entries`.
Рекомендации: `game_similarities`. Импорт: `etl_runs`.
