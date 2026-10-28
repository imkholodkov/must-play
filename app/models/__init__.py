"""Все модели собраны здесь, чтобы Alembic видел полную схему через Base.metadata."""

from app.models.catalog import Category, Developer, Genre, Language, Tag
from app.models.etl import EtlRun
from app.models.game import Game
from app.models.rating import GameScore, GameSimilarity, MustPlayEntry, RatingRun, ScoreHistory
from app.models.review import CriticReview, Outlet

__all__ = [
    "Category",
    "CriticReview",
    "Developer",
    "EtlRun",
    "Game",
    "GameScore",
    "GameSimilarity",
    "Genre",
    "Language",
    "MustPlayEntry",
    "Outlet",
    "RatingRun",
    "ScoreHistory",
    "Tag",
]
