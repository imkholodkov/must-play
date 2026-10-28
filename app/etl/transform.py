"""Превращение сырой строки CSV в запись игры и проверка её корректности."""

from dataclasses import dataclass, field
from typing import Any

from app.etl import cleaning

# Справочник → колонка CSV и функция разбора
LIST_FIELDS = {
    "genres": ("genres", cleaning.parse_list),
    "tags": ("tags", cleaning.parse_list),
    "categories": ("categories", cleaning.parse_list),
    "languages": ("supported_languages", cleaning.parse_languages),
    "developers": ("developers", cleaning.parse_list),
}


class RejectedRow(ValueError):
    """Строка не прошла проверку; причина попадает в отчёт ETL."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class GameRecord:
    game: dict[str, Any]
    lists: dict[str, list[str]] = field(default_factory=dict)


def transform_row(row: dict[str, str]) -> GameRecord:
    """Очистить строку CSV. Бросает RejectedRow, если строку нельзя загрузить."""
    app_id = cleaning.parse_int(row.get("app_id"))
    if app_id is None or app_id <= 0:
        raise RejectedRow("bad_app_id")
    name = cleaning.normalize_name(row.get("name") or "")
    if not name:
        raise RejectedRow("empty_name")

    positive = cleaning.parse_int(row.get("positive")) or 0
    negative = cleaning.parse_int(row.get("negative")) or 0
    if positive < 0 or negative < 0:
        raise RejectedRow("negative_votes")

    owners = cleaning.parse_owners(row.get("estimated_owners"))
    price = cleaning.parse_price(row.get("price"))
    game = {
        "app_id": app_id,
        "name": name[:500],
        "release_date": cleaning.parse_date(row.get("release_date")),
        "price": price,
        "is_free": row.get("price_status") == "free" or price == 0,
        "owners_min": owners[0] if owners else None,
        "owners_max": owners[1] if owners else None,
        "positive": positive,
        "negative": negative,
        "recommendations": cleaning.parse_int(row.get("recommendations")),
        "peak_ccu": cleaning.parse_int(row.get("peak_ccu")),
        "metacritic_score": cleaning.nullify_zero_score(row.get("metacritic_score")),
        "achievements": cleaning.parse_int(row.get("achievements")),
        "dlc_count": cleaning.parse_int(row.get("dlc_count")),
        "windows": cleaning.parse_bool(row.get("windows")),
        "mac": cleaning.parse_bool(row.get("mac")),
        "linux": cleaning.parse_bool(row.get("linux")),
        "short_description": (row.get("short_description") or "").strip() or None,
        "header_image": (row.get("header_image") or "").strip()[:500] or None,
    }
    lists = {key: parse(row.get(column)) for key, (column, parse) in LIST_FIELDS.items()}
    return GameRecord(game=game, lists=lists)
