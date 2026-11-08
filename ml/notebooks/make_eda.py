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
3. почему оценка игроков байесовская, а поправка прессы −7 нужна только для флага расхождения;
4. почему пороги must play — 93 / 92 и только для игр с 10 000+ голосов;
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
Порог 50 голосов (после исключения программ и дублей) оставляет 30 142 игры. Но 99% у тысячи фанатов
ещё не делает игру великой, поэтому оценка игроков байесовская, как в IMDb Top 250:
`v/(v+m)·доля + m/(v+m)·средняя по каталогу`, где m = 20 000 голосов. Пока голосов мало, оценка тянется к средней.""",
    ),
    ("md", "## 3. Пресса щедрее игроков: поправка −7 только для флага"),
    (
        "code",
        """both = sql(\"\"\"
    select s.critic_score as press, g.positive * 100.0 / (g.positive + g.negative) as players, s.player_score
    from game_scores s join games g using (app_id)
    where s.is_eligible and s.critic_score is not null
\"\"\")
print(f"игр с оценкой прессы и игроков: {len(both)}")
print(f"средняя пресса {both.press.mean():.1f}, средняя доля игроков {both.players.mean():.1f}, "
      f"оценка игроков {both.player_score.mean():.1f}")
print(f"разница пресса − доля игроков: {(both.press - both.players).mean():.1f} пункта")
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
игроков несколько пунктов, поэтому при поиске расхождений из оценки прессы вычитается 7. В сам индекс пресса
идёт без поправки: иначе игры, которые хвалят все (Witcher 3: игроки 96%, пресса 97), проседали бы.
Корреляция слабая, значит пресса и игроки дают разную информацию и их имеет смысл смешивать.""",
    ),
    ("md", "## 4. Индекс и пороги must play"),
    (
        "code",
        """index = sql(\"\"\"
    select s.index_score from game_scores s join games g using (app_id)
    where s.is_eligible and g.positive + g.negative >= 10000
\"\"\")["index_score"]
quantiles = index.quantile([0.5, 0.9, 0.95, 0.97, 0.99]).round(1)
print(quantiles.to_string())

plt.hist(index, bins=60)
for value, label in ((93, "вход 93"), (92, "выход 92")):
    plt.axvline(value, color="tab:orange", ls="--")
    plt.text(value - 1, plt.ylim()[1] * 0.9, label, ha="right")
plt.title("Индекс игр с 10 000+ голосов")
plt.xlabel("индекс")
plt.ylabel("игр")
plt.show()

for threshold in (90, 92, 93, 94, 95):
    print(f"индекс ≥ {threshold}: {(index >= threshold).sum():>5} игр ({(index >= threshold).mean():.1%})")""",
    ),
    (
        "md",
        """В must play участвуют только игры, которые знают многие: 10 000+ голосов. Порог входа 93 даёт около сотни
игр — список, который реально пройти. Порог выхода 92 ниже порога входа, чтобы игра не прыгала
туда-обратно между соседними пересчётами.""",
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
        """Модель без тегов угадывает общий редкий тег почти в 80% рекомендаций — в 1,7 раза чаще случайного выбора
и заметно чаще популярных игр. Средний индекс рекомендованных почти равен среднему по каталогу: байесовская
оценка прижимает малоизвестные игры к средней, поэтому вклад качества в ранжирование стал слабее.
Покрытие 95% — система не советует всем одни и те же хиты.""",
    ),
    ("md", "## 7. Где оказались известные игры"),
    (
        "code",
        """famous = sql(\"\"\"
    select g.name, g.positive + g.negative as votes, s.index_score,
           (select count(*) + 1 from game_scores x where x.is_eligible and x.index_score > s.index_score) as place
    from games g join game_scores s using (app_id)
    where s.is_eligible and g.name in ('The Witcher 3: Wild Hunt', 'Portal 2', 'Baldur''s Gate 3', 'Half-Life 2',
        'Stardew Valley', 'Terraria', 'Hollow Knight', 'ELDEN RING', 'Red Dead Redemption 2')
    order by place
\"\"\")
famous""",
    ),
    (
        "md",
        """## Выводы

- Без унификации форматов треть каталога потеряла бы жанры, владельцев и языки.
- Байесовская оценка игроков поднимает игры, которые и любят, и знают: Witcher 3 — 21-е место вместо 1797-го.
- Программы (Wallpaper Engine) и дубли одной игры под разными app_id в рейтинг не попадают.
- Поправка −7 нужна только для флага расхождения; с ней «перехвалила» и «недооценила» распределены почти поровну.
- Must play — около сотни игр с 10 000+ голосов и индексом от 93.
- Жанры различаются средним индексом слабо; ММО и ранний доступ заметно ниже остальных.
- Рекомендации по скрытым тегам точнее случайных в 1,7 раза и популярных игр — в 1,4 раза.""",
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
