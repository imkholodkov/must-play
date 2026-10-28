"""Разбор цитат прессы из steam_games_reviews.csv: текст, издание, оценка 0–100.

Форматы, найденные в файле:
- “Текст цитаты” 9.3/10 – MMO Games  — оценка дробью и издание;
- “Текст цитаты” 86% – GamersHell     — проценты;
- “Текст цитаты” 80 – Critically Sane — число без шкалы;
- “Текст цитаты” PC Gamer              — только издание;
- 83 – Metacritic 90 – RPGFan          — оценки без цитат (около 9% строк).
"""

import html
import re
from dataclasses import dataclass

from app.etl.cleaning import normalize_name

QUOTE_RE = re.compile(r"“(.*?)”\s*([^“]*)", re.S)
SCORE = r"\d+(?:[.,]\d+)?(?:\s*/\s*\d+|\s*%)?"
SCORE_RE = re.compile(rf"^({SCORE})\s*[–—-]\s*(.*)$")
BARE_PAIR_RE = re.compile(rf"({SCORE})\s*[–—-]\s*(.+?)(?=\s+{SCORE}\s*[–—-]|$)", re.S)
DASH_RE = re.compile(r"\s+[–—]\s+")


@dataclass(frozen=True)
class ParsedQuote:
    quote: str
    outlet: str | None
    raw_score: str | None
    score: int | None


def normalize_score(raw: str) -> int | None:
    """'4/5' → 80, '8,2/10' → 82, '86%' → 86, '7.4' → 74, '80' → 80. Вне 0–100 → None.

    Число без шкалы: до 10 включительно считается шкалой /10, больше 10 — шкалой /100.
    """
    text = raw.replace(",", ".").replace(" ", "")
    try:
        if "/" in text:
            value, scale = (float(p) for p in text.split("/"))
        else:
            value = float(text.rstrip("%"))
            scale = 100.0 if text.endswith("%") or value > 10 else 10.0
    except ValueError:
        return None
    if scale <= 0:
        return None
    score = round(value / scale * 100)
    return score if 0 <= score <= 100 else None


def outlet_key(name: str) -> str:
    """Ключ издания для поиска дублей: 'Rock, Paper, Shotgun' и 'Rock Paper Shotgun' совпадают."""
    key = re.sub(r"[^\w]+", "", html.unescape(name).casefold())
    return key.removeprefix("the")


def parse_tail(tail: str) -> tuple[str | None, str | None]:
    """Хвост после цитаты → (оценка как в источнике, издание)."""
    tail = normalize_name(tail)
    if not tail:
        return None, None
    match = SCORE_RE.match(tail)
    if match:
        return match.group(1).strip(), normalize_name(match.group(2)) or None
    # 'Eurogamer Recommends – Eurogamer': награда без оценки, издание после последнего тире
    return None, DASH_RE.split(tail)[-1].strip() or None


def parse_reviews(text: str | None) -> list[ParsedQuote]:
    """Разобрать ячейку reviews в список цитат."""
    if not text or not text.strip():
        return []
    matches = QUOTE_RE.findall(text)
    if matches:
        pairs = [(normalize_name(quote), *parse_tail(tail)) for quote, tail in matches]
    else:
        pairs = [("", raw.strip(), normalize_name(outlet)) for raw, outlet in BARE_PAIR_RE.findall(text)]
    return [
        ParsedQuote(quote=quote, outlet=outlet, raw_score=raw, score=normalize_score(raw) if raw else None)
        for quote, raw, outlet in pairs
        if quote or raw
    ]
