"""Project model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.crawl import Crawl


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A project representing a website domain to crawl."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    domain: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    settings: Mapped[dict] = mapped_column(
        sa.JSON(),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )

    # Relationships
    crawls: Mapped[list["Crawl"]] = relationship(
        "Crawl", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name!r}, domain={self.domain!r})>"
