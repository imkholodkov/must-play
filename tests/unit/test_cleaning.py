from datetime import date
from decimal import Decimal

import pytest

from app.etl import cleaning


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("100000 - 200000", (100000, 200000)),
        ("0 .. 20,000", (0, 20000)),
        ("1,000,000 .. 2,000,000", (1000000, 2000000)),
        ("", None),
        ("много", None),
        ("500 - 100", None),
    ],
)
def test_parse_owners(raw, expected):
    assert cleaning.parse_owners(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('["Adventure", "Indie"]', ["Adventure", "Indie"]),
        ('[{"id": "1", "description": "Action"}, {"id": "23", "description": "Indie"}]', ["Action", "Indie"]),
        ('{"Indie": 131, "Action": 126}', ["Indie", "Action"]),
        ("[]", []),
        ("", []),
        ("[битый json", []),
        ('["Action", "action", " Action "]', ["Action"]),
    ],
)
def test_parse_list(raw, expected):
    assert cleaning.parse_list(raw) == expected


def test_parse_list_drops_steam_placeholders():
    raw = '[{"id": 2, "description": "Single-player"}, {"id": 80, "description": "#category_playable"}]'

    assert cleaning.parse_list(raw) == ["Single-player"]


def test_parse_list_unescapes_html_entities():
    assert cleaning.parse_list('["Tom &amp; Jerry   Studio"]') == ["Tom & Jerry Studio"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('["English", "Polish"]', ["English", "Polish"]),
        ("Korean, English", ["Korean", "English"]),
        (
            "Russian<strong>*</strong>, English<br><strong>*</strong>languages with full audio support",
            ["Russian", "English"],
        ),
        ("English[b]*[/b], German", ["English", "German"]),
        (
            '["English<strong>*</strong>, French<br><strong>*</strong>languages with full audio support"]',
            ["English", "French"],
        ),
        ("", []),
    ],
)
def test_parse_languages(raw, expected):
    assert cleaning.parse_languages(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [("True", True), ("false", False), ("", None), ("maybe", None)])
def test_parse_bool(raw, expected):
    assert cleaning.parse_bool(raw) is expected


def test_parse_date():
    assert cleaning.parse_date("2018-12-20") == date(2018, 12, 20)
    assert cleaning.parse_date("") is None
    assert cleaning.parse_date("2018-13-45") is None


def test_parse_price():
    assert cleaning.parse_price("39.99") == Decimal("39.99")
    assert cleaning.parse_price("0.0") == Decimal("0.00")
    assert cleaning.parse_price("") is None
    assert cleaning.parse_price("-1") is None
    assert cleaning.parse_price("abc") is None


def test_parse_int():
    assert cleaning.parse_int("113.0") == 113
    assert cleaning.parse_int("") is None
    assert cleaning.parse_int("n/a") is None


@pytest.mark.parametrize(("raw", "expected"), [("83.0", 83), ("0.0", None), ("", None), ("150", None)])
def test_metacritic_zero_means_no_score(raw, expected):
    assert cleaning.nullify_zero_score(raw) == expected


def test_positive_share():
    assert cleaning.positive_share(9, 1) == 90.0
    assert cleaning.positive_share(0, 0) is None
