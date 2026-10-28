"""Справочники (жанры, теги, режимы, языки, разработчики) и их связи с играми M:N."""

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def link_table(name: str, ref_table: str, ref_column: str) -> Table:
    """Ассоциативная таблица game ↔ справочник с составным первичным ключом."""
    return Table(
        name,
        Base.metadata,
        Column("app_id", ForeignKey("games.app_id", ondelete="CASCADE"), primary_key=True),
        Column(ref_column, ForeignKey(f"{ref_table}.id", ondelete="CASCADE"), primary_key=True, index=True),
    )


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)


class Language(Base):
    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Developer(Base):
    __tablename__ = "developers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300), unique=True)


game_genres = link_table("game_genres", "genres", "genre_id")
game_tags = link_table("game_tags", "tags", "tag_id")
game_categories = link_table("game_categories", "categories", "category_id")
game_languages = link_table("game_languages", "languages", "language_id")
game_developers = link_table("game_developers", "developers", "developer_id")
