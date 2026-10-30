"""Игра — центральная сущность каталога."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Numeric, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.catalog import (
    Category,
    Developer,
    Genre,
    Language,
    Tag,
    game_categories,
    game_developers,
    game_genres,
    game_languages,
    game_tags,
)


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("positive >= 0 AND negative >= 0", name="votes_non_negative"),
        CheckConstraint("owners_min <= owners_max", name="owners_range"),
        CheckConstraint("metacritic_score BETWEEN 1 AND 100", name="metacritic_range"),
    )

    app_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(500), index=True)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_free: Mapped[bool] = mapped_column(default=False)
    owners_min: Mapped[int | None]
    owners_max: Mapped[int | None]
    positive: Mapped[int] = mapped_column(default=0)
    negative: Mapped[int] = mapped_column(default=0)
    recommendations: Mapped[int | None]
    peak_ccu: Mapped[int | None]
    metacritic_score: Mapped[int | None] = mapped_column(SmallInteger)
    achievements: Mapped[int | None]
    dlc_count: Mapped[int | None]
    windows: Mapped[bool | None]
    mac: Mapped[bool | None]
    linux: Mapped[bool | None]
    short_description: Mapped[str | None] = mapped_column(Text)
    header_image: Mapped[str | None] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    genres: Mapped[list[Genre]] = relationship(secondary=game_genres)
    tags: Mapped[list[Tag]] = relationship(secondary=game_tags)
    categories: Mapped[list[Category]] = relationship(secondary=game_categories)
    languages: Mapped[list[Language]] = relationship(secondary=game_languages)
    developers: Mapped[list[Developer]] = relationship(secondary=game_developers)
    score: Mapped["GameScore | None"] = relationship(viewonly=True)  # noqa: F821
