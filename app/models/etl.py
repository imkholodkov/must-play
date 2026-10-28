"""Отчёт о запуске ETL."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EtlRun(Base):
    __tablename__ = "etl_runs"
    __table_args__ = (CheckConstraint("status IN ('running', 'success', 'failed')", name="status_values"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(300))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")
    rows_read: Mapped[int] = mapped_column(default=0)
    rows_loaded: Mapped[int] = mapped_column(default=0)
    rows_updated: Mapped[int] = mapped_column(default=0)
    rows_rejected: Mapped[int] = mapped_column(default=0)
    rejection_reasons: Mapped[dict] = mapped_column(JSONB, default=dict)
