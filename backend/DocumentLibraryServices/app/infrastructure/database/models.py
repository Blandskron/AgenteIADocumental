from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, FetchedValue, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DocumentModel(Base):
    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(Text, primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[str | None] = mapped_column(Text)
    owner_area_id: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentEmbeddingModel(Base):
    __tablename__ = "document_embeddings"

    chunk_id: Mapped[str] = mapped_column(Text, primary_key=True, server_default=FetchedValue())
    document_id: Mapped[str] = mapped_column(Text, ForeignKey("documents.document_id", ondelete="CASCADE"))


class DocumentFolderModel(Base):
    __tablename__ = "document_folders"
    __table_args__ = (UniqueConstraint("owner_user_id", "parent_folder_id", "name"),)

    folder_id: Mapped[str] = mapped_column(Text, primary_key=True, server_default=FetchedValue())
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_folder_id: Mapped[str | None] = mapped_column(Text, ForeignKey("document_folders.folder_id", ondelete="CASCADE"))
    owner_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DocumentFolderItemModel(Base):
    __tablename__ = "document_folder_items"

    folder_id: Mapped[str] = mapped_column(Text, ForeignKey("document_folders.folder_id", ondelete="CASCADE"), primary_key=True)
    document_id: Mapped[str] = mapped_column(Text, ForeignKey("documents.document_id", ondelete="CASCADE"), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentFavoriteModel(Base):
    __tablename__ = "document_favorites"

    document_id: Mapped[str] = mapped_column(Text, ForeignKey("documents.document_id", ondelete="CASCADE"), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentAssignmentModel(Base):
    __tablename__ = "document_assignments"

    assignment_id: Mapped[str] = mapped_column(Text, primary_key=True, server_default=FetchedValue())
    document_id: Mapped[str] = mapped_column(Text, ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_to_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_by_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
