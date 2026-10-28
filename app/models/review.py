"""Издания прессы и их обзоры (цитаты с оценкой)."""

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Outlet(Base):
    __tablename__ = "outlets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), unique=True)


class CriticReview(Base):
    __tablename__ = "critic_reviews"
    __table_args__ = (
        UniqueConstraint("app_id", "outlet_id", name="one_review_per_outlet"),
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("games.app_id", ondelete="CASCADE"), index=True)
    outlet_id: Mapped[int | None] = mapped_column(ForeignKey("outlets.id", ondelete="SET NULL"), index=True)
    quote: Mapped[str] = mapped_column(Text)
    raw_score: Mapped[str | None] = mapped_column(String(20))
    score: Mapped[int | None] = mapped_column(SmallInteger)
