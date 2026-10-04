"""
Examination models: Exam configuration, selection rules, scoring, grading.
"""

from __future__ import annotations

import enum
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ecbtkit.db.base import Base


class ExamStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Exam(Base):
    """
    An examination definition. Holds configuration for duration, selection rules,
    scoring, grading, randomization, etc.
    """

    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)

    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    available_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    available_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    attempt_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    question_count: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    randomize_questions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    randomize_options: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    selection_rules_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    marks_correct: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    marks_wrong: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    marks_unanswered: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pass_mark: Mapped[float] = mapped_column(Float, default=40.0, nullable=False)

    grading_scale_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    result_visibility: Mapped[str] = mapped_column(String(50), default="score_percentage", nullable=False)
    show_correct_answers: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    show_explanations: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    status: Mapped[ExamStatus] = mapped_column(
        Enum(ExamStatus), default=ExamStatus.DRAFT, nullable=False, index=True
    )
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    attempts: Mapped[List["Attempt"]] = relationship(
        "Attempt", back_populates="exam", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Exam id={self.id} title={self.title!r} status={self.status}>"

    @property
    def selection_rules(self) -> Dict[str, Any]:
        if not self.selection_rules_json:
            return {}
        return json.loads(self.selection_rules_json)

    @selection_rules.setter
    def selection_rules(self, value: Dict[str, Any]) -> None:
        self.selection_rules_json = json.dumps(value) if value else None

    @property
    def grading_scale(self) -> List[Dict[str, Any]]:
        if not self.grading_scale_json:
            return []
        return json.loads(self.grading_scale_json)

    @grading_scale.setter
    def grading_scale(self, value: List[Dict[str, Any]]) -> None:
        self.grading_scale_json = json.dumps(value) if value else None

    def is_available(self, at: Optional[datetime] = None) -> bool:
        if self.status != ExamStatus.PUBLISHED:
            return False
        now = at or datetime.now(timezone.utc)
        if self.available_from and now < self.available_from.replace(tzinfo=None):
            return False
        if self.available_until and now > self.available_until.replace(tzinfo=None):
            return False
        return True
