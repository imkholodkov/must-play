"""Рейтинг: пересчёты, текущие оценки, история, must play и похожие игры."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RatingRun(Base):
    __tablename__ = "rating_runs"
    __table_args__ = (CheckConstraint("status IN ('running', 'success', 'failed')", name="status_values"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")
    games_scored: Mapped[int] = mapped_column(default=0)


class GameScore(Base):
    __tablename__ = "game_scores"
    __table_args__ = (
        CheckConstraint("divergence IN ('overrated', 'underrated')", name="divergence_values"),
        CheckConstraint("index_score BETWEEN 0 AND 100", name="index_range"),
    )

    app_id: Mapped[int] = mapped_column(ForeignKey("games.app_id", ondelete="CASCADE"), primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("rating_runs.id"))
    player_score: Mapped[float | None] = mapped_column(Float)
    critic_score: Mapped[float | None] = mapped_column(Float)
    critic_reviews_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    index_score: Mapped[float | None] = mapped_column(Float, index=True)
    is_eligible: Mapped[bool] = mapped_column(default=False, index=True)
    divergence: Mapped[str | None] = mapped_column(String(20))


class ScoreHistory(Base):
    __tablename__ = "score_history"

    run_id: Mapped[int] = mapped_column(ForeignKey("rating_runs.id", ondelete="CASCADE"), primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("games.app_id", ondelete="CASCADE"), primary_key=True, index=True)
    index_score: Mapped[float] = mapped_column(Float)


class MustPlayEntry(Base):
    __tablename__ = "must_play_entries"
    __table_args__ = (CheckConstraint("status IN ('candidate', 'in_list', 'dropped')", name="status_values"),)

    app_id: Mapped[int] = mapped_column(ForeignKey("games.app_id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("rating_runs.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GameSimilarity(Base):
    __tablename__ = "game_similarities"
    __table_args__ = (CheckConstraint("app_id <> similar_app_id", name="not_self"),)

    app_id: Mapped[int] = mapped_column(ForeignKey("games.app_id", ondelete="CASCADE"), primary_key=True)
    similar_app_id: Mapped[int] = mapped_column(ForeignKey("games.app_id", ondelete="CASCADE"), primary_key=True)
    rank: Mapped[int] = mapped_column(SmallInteger)
    score: Mapped[float] = mapped_column(Float)
