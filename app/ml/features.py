"""Признаки для ML-моделей: из сырой строки steam_games.csv или из уже готовых признаков.

Предобработка повторяет лабу 4: разбор списков и языков, флаги платформ, log1p счётчиков,
one-hot частых жанров, тегов и категорий. Голоса, рекомендации, пик онлайна и число владельцев
в признаки не входят: по ним считается целевая переменная, и модель увидела бы ответ.
"""

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

from app.etl import cleaning

NUMERIC = ["price", "is_free", "release_year", "release_month", "n_languages", "achievements", "dlc_count"]
PLATFORMS = ["windows", "mac", "linux"]
LIST_COLUMNS = {"genres": "genre", "tags": "tag", "categories": "cat"}
RAW_REQUIRED = {"release_date", "genres"}


def _row_lists(value: object) -> list[str]:
    return cleaning.parse_list(value) if isinstance(value, str) else []


class SteamFeatures(BaseEstimator, TransformerMixin):
    """Сырые колонки Steam → числовая матрица.

    В fit запоминает топ-N значений жанров, тегов и категорий; в transform строит одни и те же
    колонки для любых данных. Если на вход пришли уже готовые признаки (CSV после предобработки),
    они только выравниваются по колонкам обучения.
    """

    def __init__(self, top_genres: int = 20, top_tags: int = 60, top_categories: int = 25):
        self.top_genres = top_genres
        self.top_tags = top_tags
        self.top_categories = top_categories

    def fit(self, X: pd.DataFrame, y=None):
        limits = {"genres": self.top_genres, "tags": self.top_tags, "categories": self.top_categories}
        self.vocabulary_ = {
            column: pd.Series([v for row in X[column] for v in _row_lists(row)], dtype=object)
            .value_counts()
            .head(n)
            .index.tolist()
            for column, n in limits.items()
            if column in X
        }
        self.feature_names_ = list(self._build(X).columns)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        frame = self._build(X) if RAW_REQUIRED <= set(X.columns) else X
        missing = [c for c in self.feature_names_ if c not in frame]
        if missing:
            raise ValueError(f"нет признаков: {', '.join(missing[:5])}")
        return frame[self.feature_names_].astype(float)

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        return np.array(self.feature_names_)

    def _build(self, X: pd.DataFrame) -> pd.DataFrame:
        def col(name: str) -> pd.Series:
            return X[name].astype(str).where(X[name].notna(), "") if name in X else pd.Series("", index=X.index)

        dates = pd.to_datetime(col("release_date"), errors="coerce")
        price = col("price").map(cleaning.parse_price).astype(float).fillna(0)
        out = pd.DataFrame(index=X.index)
        out["price"] = np.log1p(price)
        out["is_free"] = ((col("price_status") == "free") | (price == 0)).astype(int)
        out["release_year"] = dates.dt.year.fillna(2018)
        out["release_month"] = dates.dt.month.fillna(6)
        out["n_languages"] = col("supported_languages").map(lambda v: len(cleaning.parse_languages(v)))
        for column in ("achievements", "dlc_count"):
            out[column] = np.log1p(col(column).map(cleaning.parse_int).astype(float).fillna(0).clip(lower=0))
        for column in PLATFORMS:
            out[column] = col(column).map(lambda v: cleaning.parse_bool(v) is True).astype(int)
        one_hot = {}
        for column, prefix in LIST_COLUMNS.items():
            values = col(column).map(lambda v: set(_row_lists(v)))
            for name in self.vocabulary_.get(column, []):
                one_hot[f"{prefix}:{name}"] = values.map(lambda s, n=name: int(n in s))
        # Колонки one-hot собираются разом: по одной они дробят DataFrame и замедляют расчёт
        return pd.concat([out, pd.DataFrame(one_hot, index=X.index)], axis=1)
