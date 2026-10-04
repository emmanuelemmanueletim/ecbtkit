"""
Examination Attempt model and related answer storage.
"""

from __future__ import annotations

import enum
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text as sql_text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ecbtkit.db.base import Base


class AttemptStatus(str, enum.Enum):
    CREATED = "created"
    ACTIVE = "active"
    SUBMITTED = "submitted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Attempt(Base):
    """
    One candidate taking one examination.
    Holds the assigned questions (version), timer, answers, and final score.
    """

    __tablename__ = "attempts"
    __table_args__ = (
        Index(
            "uq_attempt_one_active_per_candidate_exam",
            "exam_id",
            "candidate_id",
            unique=True,
            sqlite_where=sql_text("status = 'ACTIVE'"),
            postgresql_where=sql_text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[AttemptStatus] = mapped_column(
        Enum(AttemptStatus), default=AttemptStatus.CREATED, nullable=False, index=True
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    assigned_questions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    randomization_seed: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grade: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    exam: Mapped["Exam"] = relationship("Exam", back_populates="attempts")
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="attempts")
    answers: Mapped[List["Answer"]] = relationship(
        "Answer", back_populates="attempt", cascade="all, delete-orphan"
    )
    result = relationship("Result", back_populates="attempt", uselist=False)

    def __repr__(self) -> str:
        return (
            f"<Attempt id={self.id} exam={self.exam_id} "
            f"candidate={self.candidate_id} status={self.status}>"
        )

    @property
    def assigned_questions(self) -> List[Dict[str, Any]]:
        if not self.assigned_questions_json:
            return []
        return json.loads(self.assigned_questions_json)

    @assigned_questions.setter
    def assigned_questions(self, value: List[Dict[str, Any]]) -> None:
        self.assigned_questions_json = json.dumps(value) if value else None

    def is_expired(self, at: Optional[datetime] = None) -> bool:
        if self.status == AttemptStatus.EXPIRED:
            return True
        if not self.expires_at:
            return False
        now = at or datetime.now(timezone.utc)
        expires = self.expires_at
        if now.tzinfo is not None and expires.tzinfo is None:
            now = now.replace(tzinfo=None)
        elif now.tzinfo is None and expires.tzinfo is not None:
            expires = expires.replace(tzinfo=None)
        return now >= expires

    def remaining_seconds(self, at: Optional[datetime] = None) -> Optional[int]:
        if not self.expires_at or self.status != AttemptStatus.ACTIVE:
            return None
        now = at or datetime.now(timezone.utc)
        expires = self.expires_at
        if now.tzinfo is not None and expires.tzinfo is None:
            now = now.replace(tzinfo=None)
        elif now.tzinfo is None and expires.tzinfo is not None:
            expires = expires.replace(tzinfo=None)
        delta = (expires - now).total_seconds()
        return max(0, int(delta))


class Answer(Base):
    """A candidate's answer to one question within an attempt."""

    __tablename__ = "answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_answer_attempt_question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    selected_option_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    marks_awarded: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    attempt: Mapped["Attempt"] = relationship("Attempt", back_populates="answers")

    def __repr__(self) -> str:
        return f"<Answer id={self.id} attempt={self.attempt_id} question={self.question_id}>"

    @property
    def selected_ids(self) -> List[int]:
        if not self.selected_option_ids:
            return []
        try:
            data = json.loads(self.selected_option_ids)
            return [int(x) for x in data]
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    @selected_ids.setter
    def selected_ids(self, value: List[int]) -> None:
        self.selected_option_ids = json.dumps(list(value)) if value else None
