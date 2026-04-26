"""Alert model — automated alerts from crawl analysis."""

import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class Alert(UUIDPrimaryKeyMixin, Base):
    """An alert generated from crawl analysis — regressions, thresholds, etc."""

    __tablename__ = "alerts"

    project_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(),
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    crawl_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(), nullable=False
    )
    alert_type: Mapped[str] = mapped_column(
        sa.String(50), nullable=False
    )
    severity: Mapped[str] = mapped_column(
        sa.String(20), nullable=False  # critical, warning, info
    )
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text(), server_default="", nullable=False)
    metric_before: Mapped[Optional[float]] = mapped_column(sa.Float(), nullable=True)
    metric_after: Mapped[Optional[float]] = mapped_column(sa.Float(), nullable=True)
    is_read: Mapped[bool] = mapped_column(
        sa.Boolean(), server_default=sa.text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("NOW()"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, type={self.alert_type!r}, severity={self.severity!r})>"
