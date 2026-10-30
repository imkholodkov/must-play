"""Точка входа FastAPI."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import analytics, games, genres, health, ml, rating, recommendations
from app.core.config import get_settings
from app.core.errors import register_error_handlers

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title=get_settings().app_name,
    description="Рейтинг игр Steam всех времён: оценки прессы и игроков, must play и рекомендации.",
    version="0.1.0",
)
register_error_handlers(app)
for module in (health, games, genres, rating, recommendations, analytics, ml):
    app.include_router(module.router)

app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse("/ui/")
