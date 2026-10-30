"""Справочник жанров."""

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.core.database import DbSession
from app.core.errors import ConflictError
from app.models import Genre
from app.schemas.common import NamedCreate, NamedRef

router = APIRouter(prefix="/genres", tags=["genres"])


@router.get("", summary="Все жанры по алфавиту")
def list_genres(db: DbSession) -> list[NamedRef]:
    return db.scalars(select(Genre).order_by(Genre.name)).all()


@router.post(
    "", status_code=status.HTTP_201_CREATED, summary="Добавить жанр", responses={409: {"description": "Жанр уже есть"}}
)
def create_genre(data: NamedCreate, db: DbSession) -> NamedRef:
    name = data.name.strip()
    if db.scalar(select(Genre).where(func.lower(Genre.name) == name.lower())):
        raise ConflictError(f"Жанр «{name}» уже есть")
    genre = Genre(name=name)
    db.add(genre)
    db.commit()
    return genre
