"""
User / Administrator / Examiner models.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ecbtkit.db.base import Base


class UserRole(str, enum.Enum):
    CANDIDATE = "candidate"
    EXAMINER = "examiner"
    ADMINISTRATOR = "administrator"


class User(Base):
    """
    Framework user with production auth fields:
    lockout, verification, password-reset tokens.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.CANDIDATE, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Brute-force protection
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Password reset
    reset_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reset_token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
    reset_token_expires: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_token_jti: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    candidate_profile = relationship("Candidate", back_populates="user", uselist=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
