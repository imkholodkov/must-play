"""Сборка ноутбука EDA из ячеек ниже.

Запуск (нужны data/steam_games.csv и заполненная БД):
    python ml/notebooks/make_eda.py
    jupyter nbconvert --to notebook --execute --inplace ml/notebooks/eda.ipynb

Ноутбук хранится в git уже выполненным, с графиками и цифрами.
"""

from pathlib import Path

import nbformat as nbf

CELLS = [
    (
        "md",
        """# EDA: датасет Steam и обоснование правил рейтинга

Ноутбук фиксирует анализ, на котором построены очистка данных и бизнес-правила Must Play:

1. какие форматы встретились в сырых полях и почему понадобилась унификация;
2. почему порог допуска в рейтинг — 50 голосов;
3. почему оценка прессы получает поправку −7 пунктов;
4. почему пороги must play — 95 / 93;
5. как распределены расхождения прессы и игроков и средний индекс по жанрам.

Сырые форматы считаются по `data/steam_games.csv`, остальное — по БД после ETL и пересчёта рейтинга.""",
    ),
    (
        "code",
        """import csv
import json
import os
import sys
from collections import Counter

import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import create_engine

ROOT = os.path.abspath(os.path.join(os.getcwd(), "..", "..")) if os.getcwd().endswith("notebooks") else os.getcwd()
sys.path.insert(0, ROOT)
csv.field_size_limit(sys.maxsize)
plt.rcParams.update({"figure.figsize": (10, 4.5), "figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.3})

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://mustplay:change-me@localhost:5432/mustplay")
engine = create_engine(DATABASE_URL)
sql = lambda query: pd.read_sql(query, engine)  # noqa: E731""",
    ),
    ("md", "## 1. Сырые данные: какие форматы пришлось унифицировать"),
    (
        "code",
        """owners, genres, languages, rows = Counter(), Counter(), Counter(), 0
with open(os.path.join(ROOT, "data", "steam_games.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows += 1
        owners[".." if ".." in r["estimated_owners"] else "-"] += 1
        g = r["genres"].strip()
        genres["словари" if '"description"' in g else "строки"] += 1
        lang = r["supported_languages"].strip()
        if lang.startswith("[") and "<" in lang:
            languages["HTML внутри JSON"] += 1
        elif lang.startswith("["):
            languages["JSON"] += 1
        elif "<" in lang:
            languages["HTML"] += 1
        elif lang:
            languages["текст через запятую"] += 1
        else:
            languages["пусто"] += 1

print(f"строк в каталоге: {rows:,}".replace(",", " "))
pd.DataFrame(
    {
        "владельцы": pd.Series(owners),
        "жанры": pd.Series(genres),
        "языки": pd.Series(languages),
    }
).fillna(0).astype(int)""",
    ),
    (
        "md",
        """Треть каталога записана в другом формате: диапазон владельцев через «..» с запятыми, жанры списком словарей,
языки текстом с HTML. Функции `app/etl/cleaning.py` приводят все варианты к одному виду.""",
    ),
    (
        "code",
        """sql(\"\"\"
    select id, source, status, rows_read, rows_loaded, rows_updated, rows_rejected, rejection_reasons
    from etl_runs where status = 'success' order by id desc limit 4
\"\"\")""",
    ),
    ("md", "## 2. Голоса игроков и порог допуска"),
    (
        "code",
        """votes = sql("select positive, negative from games where positive + negative > 0")
votes["total"] = votes.positive + votes.negative
votes["share"] = votes.positive / votes.total * 100

fig, (a, b) = plt.subplots(1, 2)
a.hist(votes.total.clip(upper=1000), bins=50)
a.set(title="Голосов на игру (обрезано на 1000)", xlabel="голосов", ylabel="игр")
for limit, color in ((10, "tab:gray"), (50, "tab:orange")):
    sub = votes[votes.total.between(limit, limit * 3)]
    b.hist(sub.share, bins=40, alpha=0.6, label=f"{limit}–{limit * 3} голосов", color=color)
b.set(title="Доля положительных при малом числе голосов", xlabel="%")
b.legend()
plt.tight_layout()

print(f"игр с голосами: {len(votes):,}; из них 50+: {(votes.total >= 50).sum():,}".replace(",", " "))""",
    ),
    (
        "md",
        """При 10–30 голосах доля положительных разбросана почти равномерно, при 50+ распределение устойчивее.
Порог 50 голосов взят из лабораторной 6; он оставляет 30 690 игр. Дополнительно оценка игроков
считается по нижней границе интервала Уилсона, чтобы игры с малым числом голосов не выходили наверх.""",
    ),
    ("md", "## 3. Пресса щедрее игроков: поправка −7"),
    (
        "code",
        """both = sql(\"\"\"
    select s.critic_score as press, g.positive * 100.0 / (g.positive + g.negative) as players, s.player_score
    from game_scores s join games g using (app_id)
    where s.is_eligible and s.critic_score is not null
\"\"\")
print(f"игр с оценкой прессы и игроков: {len(both)}")
print(f"средняя пресса {both.press.mean():.1f}, средняя доля игроков {both.players.mean():.1f}, "
      f"оценка игроков (Уилсон) {both.player_score.mean():.1f}")
print(f"разница пресса − Уилсон: {(both.press - both.player_score).mean():.1f} пункта")
print(f"корреляция пресса / игроки: {both.press.corr(both.players):.2f}")

plt.scatter(both.players, both.press, s=6, alpha=0.4)
plt.plot([0, 100], [0, 100], color="gray", lw=1)
plt.title("Пресса против игроков (линия — полное согласие)")
plt.xlabel("доля положительных у игроков, %")
plt.ylabel("оценка прессы")
plt.show()""",
    ),
    (
        "md",
        """Большинство точек выше диагонали: пресса в среднем ставит выше, чем игроки. Средняя разница с оценкой
игроков около 7 пунктов, поэтому из оценки прессы вычитается 7 перед смешиванием в индекс и перед поиском
расхождений. Корреляция слабая, значит пресса и игроки дают разную информацию и их имеет смысл смешивать.""",
    ),
    ("md", "## 4. Индекс и пороги must play"),
    (
        "code",
        """index = sql("select index_score from game_scores where is_eligible")["index_score"]
quantiles = index.quantile([0.5, 0.9, 0.95, 0.97, 0.99]).round(1)
print(quantiles.to_string())

plt.hist(index, bins=60)
for value, label in ((95, "вход 95"), (93, "выход 93")):
    plt.axvline(value, color="tab:orange", ls="--")
    plt.text(value - 1, plt.ylim()[1] * 0.9, label, ha="right")
plt.title("Индекс допущенных игр")
plt.xlabel("индекс")
plt.ylabel("игр")
plt.show()

for threshold in (85, 90, 92, 94, 95):
    print(f"индекс ≥ {threshold}: {(index >= threshold).sum():>5} игр ({(index >= threshold).mean():.1%})")""",
    ),
    (
        "md",
        """Порог 85 давал почти треть допущенных игр — это не «обязательно сыграть». Порог входа 95 — около
97-го перцентиля, в список попадают примерно 3,5% игр. Порог выхода 93 ниже порога входа, чтобы игра
не прыгала туда-обратно между соседними пересчётами.""",
    ),
    (
        "code",
        """sql("select status, count(*) from must_play_entries group by status")""",
    ),
    ("md", "## 5. Расхождения и жанры"),
    (
        "code",
        """sql("select divergence, count(*) from game_scores where divergence is not null group by divergence")""",
    ),
    (
        "code",
        """genres = sql(\"\"\"
    select g.name as genre, count(*) as games, avg(s.index_score) as avg_index
    from genres g join game_genres gg on gg.genre_id = g.id join game_scores s on s.app_id = gg.app_id
    where s.is_eligible group by g.name having count(*) >= 300 order by avg_index
\"\"\")
plt.barh(genres.genre, genres.avg_index)
plt.xlim(60, 80)
plt.title("Средний индекс по жанрам (300+ допущенных игр)")
plt.xlabel("индекс")
plt.show()""",
    ),
    ("md", "## 6. Качество рекомендаций"),
    (
        "md",
        """Проверять похожие игры по жанрам нельзя: жанры входят в признаки, модель видела ответ.
Поэтому для оценки модель строится только по жанрам и категориям, а попадание проверяется по тегам,
которых она не видела. Слишком частые теги (у 20%+ игр) не считаются. Ту же метрику считаем для случайных
и для самых популярных игр. Расчёт — `python -m app.services.rec_metrics`, результат — `ml/rec_metrics.json`.""",
    ),
    (
        "code",
        """with open(os.path.join(ROOT, "ml", "rec_metrics.json"), encoding="utf-8") as f:
    rec = json.load(f)
precision = pd.Series(rec["tag_precision_at_10"]).rename(
    {"model_without_tags": "модель (без тегов)", "random": "случайные", "popular": "популярные"}
)
precision.plot.barh(title="Precision@10 по скрытым тегам", xlim=(0, 1))
plt.show()
pd.Series({k: v for k, v in rec.items() if k != "tag_precision_at_10"}).to_frame("значение")""",
    ),
    (
        "md",
        """Модель без тегов угадывает общий редкий тег в 80% рекомендаций — в 1,8 раза чаще случайного выбора
и заметно чаще популярных игр. Рекомендованные игры в среднем на 8 пунктов индекса лучше каталога,
то есть вклад качества в ранжирование работает. Покрытие 89% — система не советует всем одни и те же хиты.""",
    ),
    (
        "md",
        """## Выводы

- Без унификации форматов треть каталога потеряла бы жанры, владельцев и языки.
- Порог 50 голосов и оценка Уилсона защищают рейтинг от игр с горсткой голосов.
- Поправка −7 убирает систематическую щедрость прессы;
  после неё флаги «перехвалила» и «недооценила» распределены почти поровну.
- Пороги must play 95 / 93 дают короткий список около 1 000 игр.
- Жанры различаются средним индексом слабо; ММО и ранний доступ заметно ниже остальных.
- Рекомендации по скрытым тегам точнее случайных в 1,8 раза и популярных игр — в 1,4 раза.""",
    ),
]


def main() -> None:
    nb = nbf.v4.new_notebook()
    nb["cells"] = [nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src) for kind, src in CELLS]
    nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    out = Path(__file__).with_name("eda.ipynb")
    nbf.write(nb, out)
    print(out)


if __name__ == "__main__":
    main()
