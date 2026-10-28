from datetime import date
from decimal import Decimal

import pytest

from app.etl.transform import RejectedRow, transform_row

ROW = {
    "app_id": "979720",
    "name": "Big Bash Boom",
    "release_date": "2018-12-20",
    "price": "39.99",
    "price_status": "paid",
    "estimated_owners": "100000 .. 200,000",
    "positive": "10",
    "negative": "3",
    "metacritic_score": "0.0",
    "windows": "True",
    "mac": "False",
    "linux": "",
    "genres": '[{"id": "18", "description": "Sports"}]',
    "tags": '{"Sports": 12, "Cricket": 5}',
    "categories": '["Single-player", "Multi-player"]',
    "supported_languages": "English<strong>*</strong><br><strong>*</strong>languages with full audio support",
    "developers": '["Big Ant Studios"]',
}


def test_transform_cleans_all_fields():
    record = transform_row(ROW)

    assert record.game["app_id"] == 979720
    assert record.game["release_date"] == date(2018, 12, 20)
    assert record.game["price"] == Decimal("39.99")
    assert record.game["is_free"] is False
    assert (record.game["owners_min"], record.game["owners_max"]) == (100000, 200000)
    assert record.game["metacritic_score"] is None
    assert (record.game["windows"], record.game["mac"], record.game["linux"]) == (True, False, None)
    assert record.lists == {
        "genres": ["Sports"],
        "tags": ["Sports", "Cricket"],
        "categories": ["Single-player", "Multi-player"],
        "languages": ["English"],
        "developers": ["Big Ant Studios"],
    }


def test_free_game_detected_by_status():
    assert transform_row({**ROW, "price": "", "price_status": "free"}).game["is_free"] is True


@pytest.mark.parametrize(
    ("patch", "reason"),
    [
        ({"app_id": ""}, "bad_app_id"),
        ({"app_id": "-5"}, "bad_app_id"),
        ({"name": "   "}, "empty_name"),
        ({"positive": "-1"}, "negative_votes"),
    ],
)
def test_bad_rows_rejected_with_reason(patch, reason):
    with pytest.raises(RejectedRow) as exc:
        transform_row({**ROW, **patch})

    assert exc.value.reason == reason
