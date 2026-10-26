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

## Данные

Полный датасет Steam в репозиторий не входит: GitHub не принимает файлы больше 100 МБ. Файлы лежат на Google Drive с доступом по ссылке.

| Файл | Размер | Ссылка |
|---|---|---|
| `steam_games.csv` — каталог игр | 925 МБ | [Drive](https://drive.google.com/file/d/16Voa_31N5cg1n_REv9KKJXPBvKyAAPOJ/view) |
| `steam_games_reviews.csv` — цитаты прессы | 4,6 МБ | [CSV](https://drive.google.com/file/d/1YT7nzrsan8wlTijG6cx6CXLjW6aRwg2y/view), [ZIP](https://drive.google.com/file/d/1EAemIGRXGZg6F-_reWqqY7RtkWdzGGcR/view) |

Скачать оба файла в `data/`:

```bash
python -m app.etl.download_data
```

Уже скачанные файлы пропускаются, `--force` перекачивает, `--only games` или `--only reviews` скачивает один файл. ID файлов на Drive можно переопределить переменными `STEAM_GAMES_DRIVE_ID` и `STEAM_REVIEWS_DRIVE_ID`.
