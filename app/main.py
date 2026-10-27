"""Точка входа FastAPI."""

from fastapi import FastAPI

from app.api import health
from app.core.config import get_settings

app = FastAPI(
    title=get_settings().app_name,
    description="Рейтинг игр Steam всех времён: оценки прессы и игроков, must play и рекомендации.",
    version="0.1.0",
)
app.include_router(health.router)
