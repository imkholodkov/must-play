"""Очистка и унификация полей датасета Steam.

Чистые функции без обращения к БД: каждая принимает сырое значение из CSV
и возвращает значение в едином формате или None, если значения нет.
Алгоритмы перенесены из лабораторных 3, 4 и 6 курса «ИИ. Аналитика данных»
и доработаны под форматы, найденные в полном steam_games.csv.
"""

import html
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

# Steam подставляет такие строки вместо локализованных названий категорий
PLACEHOLDER_PREFIX = "#"
AUDIO_FOOTNOTE = "languages with full audio support"
TAG_RE = re.compile(r"<[^>]+>|\[/?b\]")
SPACES_RE = re.compile(r"\s+")


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
    """Булевы значения пришли строками 'True'/'False' (лаба 4); пусто → None."""
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
    """Диапазон владельцев в двух форматах (лаба 4): '0 - 20000' и '0 .. 20,000' → (0, 20000)."""
    if is_blank(value):
        return None
    parts = value.replace(",", "").replace("..", "-").split("-")
    if len(parts) != 2:
        return None
    try:
        low, high = (int(p.strip()) for p in parts)
    except ValueError:
        return None
    return (low, high) if low <= high else None


def nullify_zero_score(value: str | None) -> int | None:
    """metacritic_score: 0 означает «оценки нет» (лаба 4), а не ноль баллов."""
    score = parse_int(value)
    return score if score and 1 <= score <= 100 else None


def normalize_name(value: str) -> str:
    """Единый вид названия для справочников (лаба 3): без HTML-сущностей и лишних пробелов."""
    return SPACES_RE.sub(" ", html.unescape(value)).strip()


def dedupe(items: list[str]) -> list[str]:
    """Убрать пустые и повторы без учёта регистра, сохранив порядок."""
    seen: set[str] = set()
    result = []
    for item in items:
        name = normalize_name(item)
        key = name.casefold()
        if name and key not in seen and not name.startswith(PLACEHOLDER_PREFIX):
            seen.add(key)
            result.append(name)
    return result


def parse_list(value: str | None) -> list[str]:
    """JSON-список из CSV в трёх форматах.

    - '["Action", "Indie"]' — список строк;
    - '[{"id": "1", "description": "Action"}]' — список словарей (лаба 4, parse_genres);
    - '{"Indie": 131, "Action": 126}' — теги с числом голосов, порядок по убыванию голосов.
    Битый JSON → пустой список.
    """
    if is_blank(value):
        return []
    try:
        data = json.loads(value)
    except ValueError:
        return []
    if isinstance(data, dict):
        items = list(data)
    elif isinstance(data, list):
        items = [item.get("description", "") if isinstance(item, dict) else item for item in data]
    else:
        return []
    return dedupe([item for item in items if isinstance(item, str)])


def parse_languages(value: str | None) -> list[str]:
    """Языки в трёх форматах (лаба 4, count_languages), возвращается сам список.

    - '["English", "Polish"]' — JSON;
    - 'English, Japanese' — текст через запятую;
    - 'English<strong>*</strong><br><strong>*</strong>languages with full audio support' — текст с HTML.
    HTML-строка встречается и как единственный элемент JSON-списка, поэтому каждый элемент чистится одинаково.
    """
    if is_blank(value):
        return []
    chunks = parse_list(value) if value.lstrip().startswith("[") else [value]
    languages = []
    for chunk in chunks:
        text = chunk.split("<br>")[0] if AUDIO_FOOTNOTE in chunk else chunk
        text = TAG_RE.sub("", text).replace("*", "").replace(AUDIO_FOOTNOTE, "")
        languages.extend(re.split(r"[,\n]", text))
    return dedupe(languages)


def positive_share(positive: int, negative: int) -> float | None:
    """Доля положительных отзывов в процентах (лаба 6); без голосов → None."""
    total = positive + negative
    return round(positive / total * 100, 2) if total else None
