"""Общие помощники для тестов: подсчёт строк и фабрика игр с разумными значениями по умолчанию."""

from sqlalchemy import func, select

from app.models import Game


def count(session, model, *where) -> int:
    """Сколько строк в таблице, с необязательными условиями."""
    return session.scalar(select(func.count()).select_from(model).where(*where))


def make_game(app_id: int, name: str | None = None, positive: int = 900, negative: int = 100, **fields) -> Game:
    """Игра для теста: задаём только поля, важные для проверки, остальное — по умолчанию."""
    return Game(app_id=app_id, name=name or f"Game {app_id}", positive=positive, negative=negative, **fields)
