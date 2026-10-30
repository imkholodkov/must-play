"""Операции с играми поверх репозитория: проверки и сборка ответа."""

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import Game
from app.repositories import games as repo
from app.schemas.game import GameCreate, GameDetail, GameUpdate


def get_or_404(session: Session, app_id: int) -> Game:
    game = repo.get_game(session, app_id)
    if game is None:
        raise NotFoundError(f"Игра {app_id} не найдена")
    return game


def detail(session: Session, app_id: int) -> GameDetail:
    game = get_or_404(session, app_id)
    result = GameDetail.model_validate(game)
    result.reviews = repo.get_reviews(session, app_id)
    result.must_play_status = repo.get_must_play_status(session, app_id)
    return result


def create(session: Session, data: GameCreate) -> Game:
    if repo.get_game(session, data.app_id) is not None:
        raise ConflictError(f"Игра {data.app_id} уже есть в каталоге")
    game = Game(**data.model_dump(exclude={"genres"}))
    game.genres = repo.genres_by_names(session, data.genres)
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


def update(session: Session, app_id: int, data: GameUpdate) -> Game:
    game = get_or_404(session, app_id)
    changes = data.model_dump(exclude_unset=True)
    if "genres" in changes:
        game.genres = repo.genres_by_names(session, changes.pop("genres") or [])
    for field, value in changes.items():
        setattr(game, field, value)
    session.commit()
    session.refresh(game)
    return game


def delete(session: Session, app_id: int) -> None:
    session.delete(get_or_404(session, app_id))
    session.commit()
