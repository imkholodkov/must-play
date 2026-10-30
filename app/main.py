"""Точка входа FastAPI."""

from fastapi import FastAPI

from app.api import analytics, games, genres, health, rating, recommendations
from app.core.config import get_settings
from app.core.errors import register_error_handlers

app = FastAPI(
    title=get_settings().app_name,
    description="Рейтинг игр Steam всех времён: оценки прессы и игроков, must play и рекомендации.",
    version="0.1.0",
)
register_error_handlers(app)
for module in (health, games, genres, rating, recommendations, analytics):
    app.include_router(module.router)
