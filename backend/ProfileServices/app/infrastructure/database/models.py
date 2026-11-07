from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, FetchedValue, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    profile_id: Mapped[str] = mapped_column(Text, primary_key=True, server_default=FetchedValue())
    user_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    email: Mapped[str | None] = mapped_column(Text)
    phone_number: Mapped[str | None] = mapped_column(Text)
    profile_picture_url: Mapped[str | None] = mapped_column(Text)
    additional_info: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
