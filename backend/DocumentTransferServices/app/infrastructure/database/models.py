from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, FetchedValue, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DocumentModel(Base):
    """Read projection of shared documents; the SQL schema owns its constraints."""

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)


class DocumentAssignmentModel(Base):
    __tablename__ = "document_assignments"

    assignment_id: Mapped[str] = mapped_column(Text, primary_key=True)
    document_id: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_to_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_by_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)


class TransferEventModel(Base):
    __tablename__ = "transfer_events"

    transfer_id: Mapped[str] = mapped_column(Text, primary_key=True, server_default=FetchedValue())
    owner_user_id: Mapped[str] = mapped_column(Text, nullable=False)

    # The shared SQL schema enforces documents(document_id) ON DELETE SET NULL.
    document_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
