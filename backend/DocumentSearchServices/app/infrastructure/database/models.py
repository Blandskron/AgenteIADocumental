from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, FetchedValue, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.infrastructure.database.types import Vector


class Base(DeclarativeBase):
    pass


class DocumentModel(Base):
    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(Text, primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    chunks: Mapped[list["DocumentEmbeddingModel"]] = relationship(back_populates="document")


class DocumentEmbeddingModel(Base):
    __tablename__ = "document_embeddings"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="document_embeddings_document_chunk_unique"),)

    chunk_id: Mapped[str] = mapped_column(Text, primary_key=True, server_default=FetchedValue())
    document_id: Mapped[str] = mapped_column(Text, ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False, default="intfloat/multilingual-e5-small")
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[DocumentModel] = relationship(back_populates="chunks")


class DocumentAssignmentModel(Base):
    __tablename__ = "document_assignments"

    assignment_id: Mapped[str] = mapped_column(Text, primary_key=True, server_default=FetchedValue())
    document_id: Mapped[str] = mapped_column(Text, ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_to_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_by_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
