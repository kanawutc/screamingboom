"""Redirect model."""

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Redirect(Base):
    """A redirect hop discovered during crawling."""

    __tablename__ = "redirects"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    crawl_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(),
        sa.ForeignKey("crawls.id", ondelete="CASCADE"),
        nullable=False,
    )
    chain_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )
    source_url: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    target_url: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    status_code: Mapped[int] = mapped_column(sa.SmallInteger(), nullable=False)
    hop_number: Mapped[int] = mapped_column(sa.SmallInteger(), server_default="1", nullable=False)

    def __repr__(self) -> str:
        return f"<Redirect(id={self.id}, {self.source_url!r} -> {self.target_url!r}, status={self.status_code})>"
