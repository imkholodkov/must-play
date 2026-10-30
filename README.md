# Must Play — рейтинг игр Steam всех времён

Информационная система с REST API на FastAPI. Она отвечает на вопрос «во что поиграть»:

- **рейтинг всех времён** — одна оценка 0–100 из мнения прессы и игроков;
- **пометка расхождений** — где пресса и игроки оценивают игру по-разному;
- **must play** — список, который обновляется сам при каждом пересчёте рейтинга;
- **рекомендации** — похожие игры и подбор по анкете (жанр, режим, платформа, язык, цена);
- **ML-прогнозы** — станет ли игра хитом и как её примет пресса;
- **аналитика** — жанры, динамика по годам, строгость изданий.

Источник данных — открытый датасет Steam: 141 605 игр и 28 634 цитаты прессы. Задача минимум проекта — очистка и унификация этих данных.

Итоговый проект по дисциплине «Разработка на Python и инженерия данных». Автор — Холодков Иван. Текст задания — [docs/assignment.md](docs/assignment.md), план работ — [docs/PLAN.md](docs/PLAN.md).

| | |
|---|---|
| Отчёт о тестах (Allure) | https://imkholodkov.github.io/must-play/ |
| Покрытие кода по файлам | https://imkholodkov.github.io/must-play/coverage/ |
| Веб-интерфейс (после запуска) | http://localhost:8000/ui/ |
| Swagger (после запуска) | http://localhost:8000/docs |

## Стек

| Слой | Технологии |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| БД | PostgreSQL 16, SQLAlchemy 2, Alembic |
| Данные и ML | pandas, scikit-learn |
| Frontend | HTML, CSS, JavaScript (fetch), раздаётся самим FastAPI |
| Тесты и качество | pytest, TestClient, pytest-cov, Allure, ruff |
| Инфраструктура | Docker, docker compose, GitHub Actions, GitHub Pages |

## Быстрый старт через Docker

```bash
cp .env.example .env
docker compose up --build -d
```

Миграции применяются при старте контейнера. Дальше данные загружаются по порядку — каждая команда идемпотентна, её можно повторять:

```bash
docker compose exec app python -m app.etl.download_data        # датасет с Google Drive в data/
docker compose exec app python -m app.etl.import_data          # каталог игр (около 2 минут)
docker compose exec app python -m app.etl.import_reviews       # обзоры прессы
docker compose exec app python -m app.services.rating          # пересчёт рейтинга и must play
docker compose exec app python -m app.services.recommendations # похожие игры (около 45 секунд)
```

Must play формируется со второго пересчёта: в первом игры становятся кандидатами, во втором попадают в список. Запустите `app.services.rating` ещё раз или нажмите «Пересчитать рейтинг» на странице аналитики.

ML-модели обучаются локально (раздел «ML-модели») и лежат в `models/`, папка подключена к контейнеру. Модель можно и загрузить через `POST /ml/upload-model`.

## Локальный запуск

Нужен Python 3.12 и PostgreSQL — например, только контейнер `db` из compose:

```bash
docker compose up -d db
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://mustplay:change-me@localhost:5432/mustplay
alembic upgrade head
uvicorn app.main:app --reload
```

Команды загрузки данных те же, что выше, без `docker compose exec app`.

## Переменные окружения

Задаются в `.env`, шаблон — [.env.example](.env.example). Секретов в репозитории нет.

| Переменная | Назначение |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | учётные данные PostgreSQL в docker compose |
| `DATABASE_URL` | строка подключения SQLAlchemy; в контейнере хост `db`, локально `localhost` |
| `STEAM_GAMES_DRIVE_ID`, `STEAM_REVIEWS_DRIVE_ID` | ID файлов датасета на Google Drive |

## База данных

19 таблиц, схема создаётся и откатывается только миграциями Alembic. ERD с ключами и ограничениями — [docs/erd.md](docs/erd.md).

| Таблица | Что хранит |
|---|---|
| `games` | игра из каталога Steam: цена, дата, голоса, платформы |
| `genres`, `tags`, `categories`, `languages`, `developers` | справочники; связаны с играми M:N через `game_*` |
| `outlets` | издания прессы с нормализованным уникальным ключом |
| `critic_reviews` | цитата прессы и оценка 0–100; одно издание — один обзор на игру |
| `rating_runs` | запуски пересчёта рейтинга |
| `game_scores` | текущий индекс, оценки игроков и прессы, флаг расхождения |
| `score_history` | индекс игры в каждом пересчёте |
| `must_play_entries` | статус игры в must play |
| `game_similarities` | топ-10 похожих игр |
| `etl_runs` | отчёт каждого импорта: загружено, обновлено, отклонено и почему |

Ограничения: первичные и внешние ключи, `NOT NULL`, `UNIQUE` (названия справочников, издание + игра), `CHECK` (цена ≥ 0, голоса ≥ 0, оценки 0–100, допустимые статусы), индексы по полям поиска и сортировки.

## Бизнес-правила

Все правила — в слое `app/services/`, не в обработчиках эндпоинтов.

1. **Индекс всех времён** = 0,4 × пресса + 0,6 × игроки. Оценка игроков — нижняя граница доверительного интервала Уилсона: 3 голоса «за» из 3 дают 44, 9 000 из 10 000 — 89. Из оценки прессы вычитается 7 пунктов: на тех же играх пресса в среднем на 7 пунктов щедрее игроков. Оценка прессы учитывается при двух обзорах и больше.
2. **Допуск в рейтинг** — от 50 голосов игроков.
3. **Флаг расхождения** — если пресса (с поправкой) и доля положительных отзывов расходятся больше чем на 20 пунктов: «пресса перехвалила» или «пресса недооценила».
4. **Must play** — статусы `candidate → in_list → dropped`: вход при индексе ≥ 95, в списке остаётся при ≥ 93, ниже — выбывает; вернуться можно только через порог входа.
5. **Атомарный пересчёт** — оценки, история и must play пишутся одной транзакцией; при сбое остаётся прошлый рейтинг; второй параллельный пересчёт отклоняется с кодом 409.

Пороги подобраны по распределению данных: 95 — около 97-го перцентиля индекса, в must play попадает 1 073 игры.

## ETL: очистка и унификация данных

```bash
python -m app.etl.download_data                       # скачать датасет (ZIP 179 МБ → CSV 925 МБ)
python -m app.etl.import_data --source data/steam_games.csv
python -m app.etl.import_reviews --source data/steam_games_reviews.csv
```

Этапы: потоковое чтение CSV → проверка строки → очистка и унификация → загрузка пачками с upsert → отчёт в `etl_runs` и в лог. Алгоритмы очистки взяты из лабораторных по курсу «ИИ. Аналитика данных» и доработаны под форматы полного файла (`app/etl/cleaning.py`, `app/etl/reviews.py`):

| Проблема в данных | Как решается |
|---|---|
| владельцы в двух форматах: «0 - 20000» и «0 .. 20,000» | разбор в диапазон min / max |
| жанры и категории — списком строк или списком словарей `{"id","description"}`, теги — словарём «тег → голоса» | единый список имён без дублей и служебных заглушек `#category_…` |
| языки — JSON, текст через запятую, HTML со звёздочками | список языков: 3 587 «разных» значений → 134 |
| `metacritic_score = 0` означает «нет оценки» | NULL вместо нуля |
| оценки прессы в шкалах /5, /10, /20, /100, % | приведение к 0–100; шутки вроде 11/10 отбрасываются |
| издание записано по-разному: «Rock, Paper, Shotgun» и «Rock Paper Shotgun» | общий ключ: 11 152 написания → 9 246 изданий |
| строки без app_id или названия, дубли app_id | отклоняются, причина пишется в отчёт |

Повторный запуск дублей не создаёт: игры и обзоры обновляются, связи со справочниками перезаписываются целиком. Прерванный импорт помечается в `etl_runs` как `failed`.

## Рекомендательная система

```bash
python -m app.services.recommendations
```

- **Похожие игры** (`GET /games/{id}/similar`): TF-IDF по жанрам, тегам и категориям, косинусная близость. Итоговый порядок = 0,8 × близость + 0,2 × индекс качества, чтобы похожие, но слабые игры не выходили наверх. Например, Stardew Valley → Coral Island, My Time at Portia, Roots of Pacha.
- **Подбор по анкете** (`POST /recommendations`): жанры, теги, режим (одиночная / кооператив / мультиплеер), платформа, язык, цена, исключение уже пройденных; сортировка по индексу.

## ML-модели

```bash
python -m ml.train    # обучает обе модели на data/steam_games.csv и data/steam_games_reviews.csv
```

Признаки собираются из каталога (`app/ml/features.py`): цена, год и месяц выхода, число языков, достижения, DLC, платформы, топ-20 жанров, топ-60 тегов, топ-25 категорий. Голоса, рекомендации, онлайн и число владельцев в признаки не входят — по ним считается цель. Разделение train/test — 80/20 со стратификацией.

| Модель | Цель | Игр | LogReg | Random Forest | Gradient Boosting |
|---|---|---|---|---|---|
| `hit` | верхние 10% по оценке игроков среди игр с 10+ голосами | 56 763 | 0,776 | 0,804 | **0,804** |
| `press` | средняя оценка прессы 75+ | 5 875 | 0,695 | **0,740** | 0,709 |

Метрика — ROC-AUC на отложенных 20%. Лучшая модель сохраняется в `models/<модель>.pkl`, все метрики — в [ml/metrics.json](ml/metrics.json).

- `POST /ml/upload-model` — форма `model` (`hit` | `press`) и файл `.pkl`; ответ `{"status": "success", ...}` или ошибка 400. Файл pkl при загрузке исполняет код, поэтому загружайте только свои модели.
- `POST /ml/predict` — одна или несколько записей (сырые колонки steam_games.csv или готовые признаки); в ответ добавляются `<модель>_probability` и `<модель>_predicted`. Без загруженной модели — 503.
- `POST /ml/predict-from-csv` — CSV сырой или предобработанный; если есть колонка `target` (0/1), возвращается ROC-AUC, плюс весь датасет с прогнозом.

## REST API

Полный список с описаниями и примерами — в Swagger: http://localhost:8000/docs. Ошибки всегда приходят в одном формате:

```json
{"error": {"code": "not_found", "message": "Игра 999 не найдена", "details": null}}
```

| Группа | Эндпоинты |
|---|---|
| Игры | `GET /games` (фильтры, сортировка, пагинация), `GET /games/{id}`, `POST /games`, `PATCH /games/{id}`, `DELETE /games/{id}` |
| Справочники | `GET /genres`, `POST /genres` |
| Рейтинг | `GET /rating`, `GET /must-play`, `POST /rating/recalculate`, `GET /rating/runs` |
| Рекомендации | `GET /games/{id}/similar`, `POST /recommendations` |
| Аналитика | `GET /analytics/genres`, `GET /analytics/releases`, `GET /analytics/divergence`, `GET /analytics/outlets` |
| ML | `POST /ml/upload-model`, `POST /ml/predict`, `POST /ml/predict-from-csv` |
| Служебное | `GET /health` |

Примеры запросов:

```bash
# Топ-3 RPG 2010-х
curl "http://localhost:8000/rating?genre=RPG&decade=2010&limit=3"

# Список игр: поиск, фильтр по платформе, сортировка по дате
curl "http://localhost:8000/games?q=knight&platform=linux&sort=release_date&limit=5"

# Карточка игры с обзорами прессы и статусом must play
curl "http://localhost:8000/games/504230"

# Подбор: кооперативная RPG на русском до 20 $
curl -X POST http://localhost:8000/recommendations -H "Content-Type: application/json" \
  -d '{"genres": ["RPG"], "mode": "coop", "language": "Russian", "max_price": "20", "limit": 5}'

# Добавить игру (201) и повторить (409)
curl -X POST http://localhost:8000/games -H "Content-Type: application/json" \
  -d '{"app_id": 999000001, "name": "Моя игра", "price": "4.99", "genres": ["Indie"]}'

# Пересчитать рейтинг
curl -X POST http://localhost:8000/rating/recalculate

# Где пресса сильнее всего перехвалила игру
curl "http://localhost:8000/analytics/divergence?kind=overrated&limit=5"

# Прогноз ML по CSV с колонкой target
curl -X POST http://localhost:8000/ml/predict-from-csv -F model=hit -F file=@games.csv
```

## Тесты

```bash
ruff check . && ruff format --check .
pytest
```

- Unit-тесты: очистка данных, разбор цитат и шкал, бизнес-правила рейтинга, признаки ML.
- Интеграционные тесты: ETL на тестовой БД, все группы эндпоинтов, включая ошибки 400, 404, 409, 422 и 503.
- Тесты с БД работают в транзакции, которая откатывается после каждого теста. Запускайте их на отдельной базе; без PostgreSQL они пропускаются:

```bash
docker compose exec db psql -U mustplay -c "create database mustplay_test"
DATABASE_URL=postgresql+psycopg://mustplay:change-me@localhost:5432/mustplay_test pytest
```

`pytest` считает покрытие и падает, если оно ниже 70%; сейчас покрытие 94%. GitHub Actions на каждый push и PR запускает ruff и pytest, а для main собирает отчёт Allure с историей прогонов и HTML-отчёт покрытия и публикует их на GitHub Pages. Локально отчёт Allure:

```bash
pytest --alluredir allure-results
allure serve allure-results
```

## Структура

```
app/
  api/           роутеры
  core/          конфигурация, подключение к БД, единый формат ошибок
  etl/           скачивание, очистка, импорт каталога и обзоров
  ml/            признаки и хранилище моделей
  models/        SQLAlchemy-модели
  repositories/  запросы к БД: фильтры, пагинация, аналитика
  schemas/       Pydantic-схемы
  services/      бизнес-логика: рейтинг, рекомендации, операции с играми
frontend/        веб-интерфейс
migrations/      миграции Alembic
ml/              обучение моделей и метрики
models/          обученные модели (pkl, не в git)
tests/           unit- и интеграционные тесты
data/sample/     выборка датасета на 305 строк для тестов
docs/            задание, план, ERD
```
