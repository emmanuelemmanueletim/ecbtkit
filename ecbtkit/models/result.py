"""
Examination Result model.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ecbtkit.db.base import Base


class Result(Base):
    """
    Structured result produced after an attempt is marked.
    Visibility of fields to candidates is controlled by the Exam configuration.
    """

    __tablename__ = "results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )

    score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    grade: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)

    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unanswered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    time_used_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    breakdown_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    attempt = relationship("Attempt", back_populates="result")
    exam = relationship("Exam")
    candidate = relationship("Candidate")

    def __repr__(self) -> str:
        return f"<Result id={self.id} score={self.score}/{self.max_score} passed={self.passed}>"

    @property
    def breakdown(self) -> Dict[str, Any]:
        if not self.breakdown_json:
            return {}
        return json.loads(self.breakdown_json)

    @breakdown.setter
    def breakdown(self, value: Dict[str, Any]) -> None:
        self.breakdown_json = json.dumps(value) if value else None
