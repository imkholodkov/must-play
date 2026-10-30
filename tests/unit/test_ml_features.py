import pandas as pd
import pytest

from app.ml.features import SteamFeatures

RAW = pd.DataFrame(
    [
        {
            "release_date": "2018-01-25",
            "price": "19.99",
            "genres": '["Action", "Indie"]',
            "tags": '{"Platformer": 10}',
            "categories": '["Single-player"]',
            "supported_languages": "English, Russian",
            "windows": "True",
            "mac": "False",
            "linux": "",
            "achievements": "30",
            "dlc_count": "",
        },
        {"release_date": "", "price": "", "genres": "[]", "tags": "", "categories": "", "supported_languages": ""},
    ]
)


def test_raw_rows_become_numeric_features():
    features = SteamFeatures(top_genres=2, top_tags=1, top_categories=1).fit(RAW)
    out = features.transform(RAW)

    assert list(out.columns[-4:]) == ["genre:Action", "genre:Indie", "tag:Platformer", "cat:Single-player"]
    first = out.iloc[0]
    assert (first["release_year"], first["n_languages"], first["windows"], first["mac"]) == (2018, 2, 1, 0)
    assert out.iloc[1]["release_year"] == 2018  # пропуск даты заполнен
    assert not out.isna().any().any()


def test_preprocessed_features_pass_through():
    features = SteamFeatures(top_genres=2, top_tags=1, top_categories=1).fit(RAW)
    prepared = features.transform(RAW)

    assert features.transform(prepared).equals(prepared)


def test_missing_features_reported():
    features = SteamFeatures().fit(RAW)

    with pytest.raises(ValueError, match="нет признаков"):
        features.transform(pd.DataFrame([{"foo": 1}]))
