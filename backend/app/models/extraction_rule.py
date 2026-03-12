import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExtractionRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "extraction_rules"

    project_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(),
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    selector: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    selector_type: Mapped[str] = mapped_column(sa.String(10), server_default="css", nullable=False)
    extract_type: Mapped[str] = mapped_column(sa.String(20), server_default="text", nullable=False)
    attribute_name: Mapped[Optional[str]] = mapped_column(sa.String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<ExtractionRule(id={self.id}, name={self.name!r}, selector={self.selector!r})>"
