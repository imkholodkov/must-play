"""CRUD игр: список с фильтрами и пагинацией, карточка, создание, правка, удаление."""

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status

from app.core.database import DbSession
from app.core.errors import error_body
from app.repositories import games as repo
from app.repositories.games import GameFilters, SortField
from app.schemas.common import Page
from app.schemas.game import GameCreate, GameDetail, GameRead, GameUpdate
from app.services import games as service

router = APIRouter(prefix="/games", tags=["games"])

ERRORS_404 = {
    404: {
        "description": "Игра не найдена",
        "content": {"application/json": {"example": error_body("not_found", "Игра 42 не найдена")}},
    }
}


@router.get("", summary="Список игр с фильтрами, сортировкой и пагинацией")
def list_games(
    db: DbSession,
    q: Annotated[str | None, Query(description="Поиск по названию", examples=["hollow"])] = None,
    genre: Annotated[str | None, Query(description="Жанр", examples=["Indie"])] = None,
    platform: Annotated[Literal["windows", "mac", "linux"] | None, Query(description="Платформа")] = None,
    year_from: Annotated[int | None, Query(ge=1970, le=2100)] = None,
    year_to: Annotated[int | None, Query(ge=1970, le=2100)] = None,
    max_price: Annotated[Decimal | None, Query(ge=0)] = None,
    free: bool | None = None,
    eligible: Annotated[bool | None, Query(description="Только допущенные в рейтинг")] = None,
    divergence: Annotated[Literal["overrated", "underrated"] | None, Query(description="Флаг расхождения")] = None,
    sort: SortField = SortField.index,
    desc: bool = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[GameRead]:
    filters = GameFilters(q, genre, platform, year_from, year_to, max_price, free, eligible, divergence)
    items, total = repo.list_games(db, filters, sort, desc, limit, offset)
    return Page[GameRead](items=items, total=total, limit=limit, offset=offset)


@router.get("/{app_id}", summary="Карточка игры: оценки, обзоры прессы, статус must play", responses=ERRORS_404)
def get_game(app_id: int, db: DbSession) -> GameDetail:
    return service.detail(db, app_id)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить игру вручную",
    responses={409: {"description": "Игра с таким app_id уже есть"}},
)
def create_game(data: GameCreate, db: DbSession) -> GameRead:
    return service.create(db, data)


@router.patch("/{app_id}", summary="Исправить данные игры", responses=ERRORS_404)
def update_game(app_id: int, data: GameUpdate, db: DbSession) -> GameRead:
    return service.update(db, app_id, data)


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить игру", responses=ERRORS_404)
def delete_game(app_id: int, db: DbSession) -> Response:
    service.delete(db, app_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
