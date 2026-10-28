import pytest

from app.etl.reviews import ParsedQuote, normalize_score, outlet_key, parse_reviews


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("4/5", 80),
        ("9.3/10", 93),
        ("8,2/10", 82),
        ("7.5 / 10", 75),
        ("82/100", 82),
        ("17/20", 85),
        ("86%", 86),
        ("7.4", 74),
        ("80", 80),
        ("11/10", None),
        ("9000", None),
        ("5/0", None),
    ],
)
def test_normalize_score(raw, expected):
    assert normalize_score(raw) == expected


@pytest.mark.parametrize(
    "spelling",
    ["Rock Paper Shotgun", "Rock, Paper, Shotgun", "ROCK PAPER SHOTGUN", "The Rock Paper Shotgun", "Rock&amp;Paper"],
)
def test_outlet_key_merges_spellings(spelling):
    expected = "rockpaper" if "amp" in spelling else "rockpapershotgun"
    assert outlet_key(spelling) == expected


def test_parse_quotes_with_score_and_outlet():
    text = "“Great game.” 9.3/10 – MMO Games “Fun!” PC Gamer “Awful.” 4/5 – SKNR"

    assert parse_reviews(text) == [
        ParsedQuote("Great game.", "MMO Games", "9.3/10", 93),
        ParsedQuote("Fun!", "PC Gamer", None, None),
        ParsedQuote("Awful.", "SKNR", "4/5", 80),
    ]


def test_award_without_score_keeps_outlet_after_dash():
    assert parse_reviews("“Brilliant” Eurogamer Recommends – Eurogamer") == [
        ParsedQuote("Brilliant", "Eurogamer", None, None)
    ]


def test_scores_without_quotes():
    assert parse_reviews("83 – Metacritic 90 – Digitally Downloaded 85 – RPGFan") == [
        ParsedQuote("", "Metacritic", "83", 83),
        ParsedQuote("", "Digitally Downloaded", "90", 90),
        ParsedQuote("", "RPGFan", "85", 85),
    ]


@pytest.mark.parametrize("text", ["", None, "   ", "RECOMMENDED – Steam Curator"])
def test_nothing_to_parse(text):
    assert parse_reviews(text) == []
