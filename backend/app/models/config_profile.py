"""Configuration Profile model — reusable crawl presets."""

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ConfigProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A saved crawl configuration profile."""

    __tablename__ = "config_profiles"

    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[str] = mapped_column(sa.String(500), server_default="", nullable=False)
    config: Mapped[dict] = mapped_column(
        sa.JSON(),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )
    is_default: Mapped[bool] = mapped_column(
        sa.Boolean(), server_default=sa.text("false"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ConfigProfile(id={self.id}, name={self.name!r})>"
