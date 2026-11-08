"""Очистка и унификация полей датасета Steam.

Чистые функции без обращения к БД: каждая принимает сырое значение из CSV
и возвращает значение в едином формате или None, если значения нет.
Правила разбора подобраны под форматы, найденные в полном steam_games.csv.
"""

import html
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

# Steam подставляет такие строки вместо локализованных названий категорий
PLACEHOLDER_PREFIX = "#"
AUDIO_FOOTNOTE = "languages with full audio support"
AUDIO_FOOTNOTES = (AUDIO_FOOTNOTE, "idiomas con localización de audio")
TAG_RE = re.compile(r"<[^>]+>|\[/?b\]")
SPACES_RE = re.compile(r"\s+")
PARENS_RE = re.compile(r"\s*\([^)]*\)")

# Названия языков на других языках интерфейса Steam → английское название
LANGUAGE_SYNONYMS = {
    "anglais": "English",
    "inglés": "English",
    "英語": "English",
    "français": "French",
    "allemand": "German",
    "espagnol - espagne": "Spanish - Spain",
    "スペイン語 - スペイン": "Spanish - Spain",
    "russe": "Russian",
    "ロシア語": "Russian",
    "polonais": "Polish",
    "coréen": "Korean",
    "japonais": "Japanese",
    "日本語": "Japanese",
    "ukrainien": "Ukrainian",
    "portugais du brésil": "Portuguese - Brazil",
    "chinois simplifié": "Simplified Chinese",
    "chineză simplificată": "Simplified Chinese",
    "中国語（簡体字）": "Simplified Chinese",
    "chineză tradițională": "Traditional Chinese",
}


def unescape_all(value: str) -> str:
    """Снять HTML-экранирование, в том числе многократное: '&amp;amp;lt;' → '<'."""
    previous = None
    while previous != value:
        previous, value = value, html.unescape(value)
    return value


def is_blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def parse_int(value: str | None) -> int | None:
    """'1234', '1234.0' → 1234; пусто или мусор → None."""
    if is_blank(value):
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_price(value: str | None) -> Decimal | None:
    """'39.99' → Decimal('39.99'); пусто или отрицательное → None."""
    if is_blank(value):
        return None
    try:
        price = Decimal(value.strip()).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return price if price >= 0 else None


def parse_bool(value: str | None) -> bool | None:
    """Булевы значения пришли строками 'True'/'False'; пусто → None."""
    if is_blank(value):
        return None
    return {"true": True, "false": False}.get(value.strip().lower())


def parse_date(value: str | None) -> date | None:
    """ISO-дата 'YYYY-MM-DD'; пусто или битая дата → None (строка не отбрасывается)."""
    if is_blank(value):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def parse_owners(value: str | None) -> tuple[int, int] | None:
    """Диапазон владельцев в двух форматах: '0 - 20000' и '0 .. 20,000' → (0, 20000)."""
    if is_blank(value):
        return None
    # «0 .. 20,000» превращаем в «0 - 20000», дальше оба формата разбираются одинаково
    parts = value.replace(",", "").replace("..", "-").split("-")
    if len(parts) != 2:
        return None
    try:
        low, high = (int(p.strip()) for p in parts)
    except ValueError:
        return None
    return (low, high) if low <= high else None


def nullify_zero_score(value: str | None) -> int | None:
    """metacritic_score: 0 означает «оценки нет», а не ноль баллов."""
    score = parse_int(value)
    return score if score and 1 <= score <= 100 else None


def normalize_name(value: str) -> str:
    """Единый вид названия для справочников: без HTML-сущностей и лишних пробелов."""
    return SPACES_RE.sub(" ", html.unescape(value)).strip()


def dedupe(items: list[str]) -> list[str]:
    """Убрать пустые и повторы без учёта регистра, сохранив порядок."""
    seen: set[str] = set()
    result = []
    for item in items:
        name = normalize_name(item)
        # сравниваем без регистра: «Action» и «action» — один жанр
        key = name.casefold()
        if name and key not in seen and not name.startswith(PLACEHOLDER_PREFIX):
            seen.add(key)
            result.append(name)
    return result


def parse_list(value: str | None) -> list[str]:
    """JSON-список из CSV в трёх форматах.

    - '["Action", "Indie"]' — список строк;
    - '[{"id": "1", "description": "Action"}]' — список словарей;
    - '{"Indie": 131, "Action": 126}' — теги с числом голосов, порядок по убыванию голосов.
    Битый JSON → пустой список.
    """
    if is_blank(value):
        return []
    try:
        data = json.loads(value)
    except ValueError:
        return []
    # теги иногда приходят словарём «тег → число голосов», нам нужны только ключи
    if isinstance(data, dict):
        items = list(data)
    elif isinstance(data, list):
        items = [item.get("description", "") if isinstance(item, dict) else item for item in data]
    else:
        return []
    return dedupe([item for item in items if isinstance(item, str)])


def parse_languages(value: str | None) -> list[str]:
    """Языки в трёх форматах, возвращается сам список.

    - '["English", "Polish"]' — JSON;
    - 'English, Japanese' — текст через запятую;
    - 'English<strong>*</strong><br><strong>*</strong>languages with full audio support' — текст с HTML.
    HTML-строка встречается и как единственный элемент JSON-списка, в том числе экранированная несколько раз,
    поэтому каждый элемент чистится одинаково. Пометки в скобках «(full audio)» отбрасываются,
    названия на других языках интерфейса сводятся к английским по LANGUAGE_SYNONYMS.
    """
    if is_blank(value):
        return []
    chunks = parse_list(value) if value.lstrip().startswith("[") else [value]
    languages = []
    for chunk in chunks:
        text = unescape_all(chunk)
        if any(note in text for note in AUDIO_FOOTNOTES):
            text = re.split(r"<br\s*/?>", text)[0]
        text = TAG_RE.sub("", text).replace("*", "")
        for note in AUDIO_FOOTNOTES:
            text = text.replace(note, "")
        text = PARENS_RE.sub("", text)
        languages.extend(re.split(r"[,;\n]", text))
    return dedupe([LANGUAGE_SYNONYMS.get(name.strip().casefold(), name) for name in languages])


def positive_share(positive: int, negative: int) -> float | None:
    """Доля положительных отзывов в процентах; без голосов → None."""
    total = positive + negative
    return round(positive / total * 100, 2) if total else None
