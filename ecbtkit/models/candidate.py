"""
Candidate model — a person taking examinations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ecbtkit.db.base import Base


class Candidate(Base):
    """
    Represents a candidate who can take examinations.
    Linked optionally to a User account for authentication.
    """

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    registration_number: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="candidate_profile")
    attempts = relationship("Attempt", back_populates="candidate", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Candidate id={self.id} name={self.full_name!r}>"
