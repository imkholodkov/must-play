"""Обучение двух классификаторов и выбор лучшего алгоритма по ROC-AUC.

Модели:
- hit   — станет ли игра хитом: верхние 10% по нижней границе Уилсона среди игр с 10+ голосами;
- press — оценит ли пресса игру на 75+ (средняя оценка из обзоров, только игры с оценками).

Для каждой цели сравниваются логистическая регрессия, случайный лес и градиентный бустинг.
Лучший пайплайн (признаки + модель) сохраняется в models/<target>.pkl, метрики — в ml/metrics.json.

Запуск: python -m ml.train --games data/steam_games.csv --reviews data/steam_games_reviews.csv
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.etl.reviews import parse_reviews
from app.ml.features import SteamFeatures
from app.services.scoring import wilson_lower_bound

logger = logging.getLogger(__name__)
csv.field_size_limit(sys.maxsize)

FEATURE_COLUMNS = [
    "app_id", "release_date", "price", "price_status", "supported_languages", "achievements", "dlc_count",
    "windows", "mac", "linux", "genres", "tags", "categories", "positive", "negative",
]  # fmt: skip
MIN_VOTES_HIT = 10
HIT_QUANTILE = 0.9
PRESS_THRESHOLD = 75
RANDOM_STATE = 42


def load_games(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, usecols=FEATURE_COLUMNS, dtype=str, keep_default_na=False)


def critic_scores(path: Path) -> pd.Series:
    """Средняя оценка прессы по игре (только цитаты с числовой оценкой)."""
    rows = pd.read_csv(path, dtype=str, keep_default_na=False)
    means = {}
    for app_id, text in zip(rows["app_id"], rows["reviews"], strict=True):
        scores = [q.score for q in parse_reviews(text) if q.score is not None]
        if scores:
            means[app_id] = float(np.mean(scores))
    return pd.Series(means, name="critic_score")


def hit_dataset(games: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, dict]:
    votes = games[["positive", "negative"]].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    games = games[votes.sum(axis=1) >= MIN_VOTES_HIT]
    votes = votes.loc[games.index]
    wilson = [wilson_lower_bound(p, n) for p, n in zip(votes["positive"], votes["negative"], strict=True)]
    wilson = pd.Series(wilson, index=games.index)
    threshold = float(wilson.quantile(HIT_QUANTILE))
    return games, (wilson >= threshold).astype(int), {"min_votes": MIN_VOTES_HIT, "wilson_threshold": threshold}


def press_dataset(games: pd.DataFrame, critic: pd.Series) -> tuple[pd.DataFrame, pd.Series, dict]:
    games = games[games["app_id"].isin(critic.index)]
    target = (games["app_id"].map(critic) >= PRESS_THRESHOLD).astype(int)
    return games, target, {"press_threshold": PRESS_THRESHOLD}


def candidates() -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline(
            [("features", SteamFeatures()), ("scale", StandardScaler()),
             ("model", LogisticRegression(max_iter=2000, class_weight="balanced"))]
        ),
        "random_forest": Pipeline(
            [("features", SteamFeatures()),
             ("model", RandomForestClassifier(n_estimators=300, min_samples_leaf=5, n_jobs=-1,
                                              class_weight="balanced", random_state=RANDOM_STATE))]
        ),
        "gradient_boosting": Pipeline(
            [("features", SteamFeatures()),
             ("model", HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=RANDOM_STATE))]
        ),
    }  # fmt: skip


def train_target(name: str, X: pd.DataFrame, y: pd.Series, info: dict, out_dir: Path) -> dict:
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)
    results = {}
    best_name, best_auc, best_pipe = None, -1.0, None
    for algo, pipe in candidates().items():
        pipe.fit(X_train, y_train)
        auc = roc_auc_score(y_test, pipe.predict_proba(X_test)[:, 1])
        results[algo] = round(float(auc), 4)
        logger.info("%s / %s: ROC-AUC %.4f", name, algo, auc)
        if auc > best_auc:
            best_name, best_auc, best_pipe = algo, auc, pipe
    if best_pipe is None:
        raise ValueError(f"{name}: ROC-AUC не посчитан — в тестовой выборке один класс, данных мало")
    joblib.dump(best_pipe, out_dir / f"{name}.pkl")
    return {
        "best": best_name,
        "roc_auc": results,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "positive_share": round(float(y.mean()), 3),
        "features": len(best_pipe.named_steps["features"].feature_names_),
        **info,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Обучить модели hit и press")
    parser.add_argument("--games", type=Path, default=Path("data/steam_games.csv"))
    parser.add_argument("--reviews", type=Path, default=Path("data/steam_games_reviews.csv"))
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--metrics", type=Path, default=Path("ml/metrics.json"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    args.models_dir.mkdir(exist_ok=True)
    games = load_games(args.games)
    metrics = {
        "hit": train_target("hit", *hit_dataset(games), args.models_dir),
        "press": train_target("press", *press_dataset(games, critic_scores(args.reviews)), args.models_dir),
    }
    args.metrics.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("Метрики: %s", json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
