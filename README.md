# Must Play — рейтинг игр всех времён

Информационная система с REST API на FastAPI: рейтинг игр Steam по оценкам прессы и игроков, кураторский список must play, подбор «во что поиграть» и ML-прогнозы.

Итоговый проект по дисциплине «Разработка на Python и инженерия данных». Текст задания — [docs/assignment.md](docs/assignment.md).

## Структура

| Папка | Назначение |
|---|---|
| `app/api` | роутеры |
| `app/models` | SQLAlchemy-модели |
| `app/schemas` | Pydantic-схемы |
| `app/services` | бизнес-логика |
| `app/repositories` | доступ к БД |
| `app/etl` | импорт и очистка данных |
| `app/ml` | загрузка модели и прогноз |
| `app/core` | конфигурация |
| `ml/` | EDA и обучение моделей |
| `models/` | сохранённые модели (pkl, не в git) |
| `migrations/` | миграции Alembic |
| `tests/` | unit- и интеграционные тесты |
| `frontend/` | HTML/JS-интерфейс |
| `data/sample/` | выборка датасета для тестов |
| `docs/` | задание, ERD, отчёты |

## Запуск

Через Docker (приложение и PostgreSQL):

```bash
cp .env.example .env
docker compose up --build
```

Локально (нужен Python 3.12 и запущенный PostgreSQL):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Проверка: http://localhost:8000/health, документация API — http://localhost:8000/docs.

## Рейтинг и рекомендации

После импорта данных:

```bash
python -m app.services.rating            # пересчёт индексов, флагов и must play (атомарно)
python -m app.services.recommendations   # похожие игры для рекомендаций
```

Похожие игры: TF-IDF по жанрам, тегам и категориям, косинусная близость (scikit-learn), топ-10 для каждой допущенной игры. Итоговый порядок = 0,8 × близость + 0,2 × индекс качества. Подбор по анкете (`POST /recommendations`) фильтрует допущенные игры по жанрам, тегам, режиму (одиночная / кооператив / мультиплеер), платформе, языку и цене и сортирует по индексу.

## Тесты и линтинг

```bash
ruff check . && ruff format --check .
pytest
```

Тесты с БД работают в транзакции, которая откатывается после каждого теста. Запускайте их на отдельной базе, иначе данные основной БД попадут в проверки:

```bash
docker compose exec db psql -U mustplay -c "create database mustplay_test"
DATABASE_URL=postgresql+psycopg://mustplay:change-me@localhost:5432/mustplay_test pytest
```

Если PostgreSQL недоступен, тесты с БД пропускаются.

`pytest` считает покрытие и падает, если оно ниже 70%. Те же проверки запускает GitHub Actions на каждый push и PR.

## Переменные окружения

| Переменная | Назначение |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | учётные данные PostgreSQL в docker compose |
| `DATABASE_URL` | строка подключения SQLAlchemy |
| `STEAM_GAMES_DRIVE_ID`, `STEAM_REVIEWS_DRIVE_ID` | ID файлов датасета на Google Drive |

## Данные

Полный датасет Steam в репозиторий не входит: GitHub не принимает файлы больше 100 МБ. Файлы лежат на Google Drive с доступом по ссылке.

| Файл | Размер | Ссылка |
|---|---|---|
| `steam_games.csv` — каталог игр | 925 МБ, в ZIP 179 МБ | [CSV](https://drive.google.com/file/d/16Voa_31N5cg1n_REv9KKJXPBvKyAAPOJ/view), [ZIP](https://drive.google.com/file/d/1yVfu0xU3bqR6qka_CoFak5tw-D1TUEAw/view) |
| `steam_games_reviews.csv` — цитаты прессы | 4,6 МБ | [CSV](https://drive.google.com/file/d/1YT7nzrsan8wlTijG6cx6CXLjW6aRwg2y/view), [ZIP](https://drive.google.com/file/d/1EAemIGRXGZg6F-_reWqqY7RtkWdzGGcR/view) |

Скачать оба файла в `data/`:

```bash
python -m app.etl.download_data
```

Выборка из 305 строк для тестов лежит в `data/sample/steam_games_sample.csv`.

### Импорт в БД (ETL)

```bash
python -m app.etl.import_data --source data/steam_games.csv
```

Этапы: потоковое чтение CSV → проверка строки (нет app_id или названия, отрицательные голоса, дубль app_id — строка отклоняется с причиной) → очистка и унификация (`app/etl/cleaning.py`) → загрузка пачками с upsert по `app_id` → отчёт в таблице `etl_runs`. Повторный запуск дублей не создаёт: игры обновляются, связи со справочниками перезаписываются.

После каталога загружаются обзоры прессы:

```bash
python -m app.etl.import_reviews --source data/steam_games_reviews.csv
```

Цитаты разбираются на текст, издание и оценку (`app/etl/reviews.py`). Оценки из шкал /5, /10, /20, /100 и % приводятся к 0–100. Названия изданий сводятся к одному ключу: «Rock, Paper, Shotgun» и «Rock Paper Shotgun» — одно издание. Одно издание — один обзор на игру. Обзоры игр, которых нет в каталоге, отклоняются с причиной `unknown_game`.

Уже скачанные файлы пропускаются, `--force` перекачивает, `--only games` или `--only reviews` скачивает один файл. ID файлов на Drive можно переопределить переменными `STEAM_GAMES_DRIVE_ID` и `STEAM_REVIEWS_DRIVE_ID`.
