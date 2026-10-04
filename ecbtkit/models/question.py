"""
Question bank models: Subject, Topic, Question, Option.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ecbtkit.db.base import Base


class Difficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class QuestionType(str, enum.Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"


class Subject(Base):
    """Top-level classification for questions (e.g. Mathematics, Physics)."""

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    topics: Mapped[List["Topic"]] = relationship(
        "Topic", back_populates="subject", cascade="all, delete-orphan"
    )
    questions: Mapped[List["Question"]] = relationship("Question", back_populates="subject")

    def __repr__(self) -> str:
        return f"<Subject id={self.id} name={self.name!r}>"


class Topic(Base):
    """Second-level classification under a Subject."""

    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("subject_id", "name", name="uq_topic_subject_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    subject: Mapped["Subject"] = relationship("Subject", back_populates="topics")
    questions: Mapped[List["Question"]] = relationship("Question", back_populates="topic")

    def __repr__(self) -> str:
        return f"<Topic id={self.id} name={self.name!r}>"


class Question(Base):
    """
    Core question entity. Prioritizes objective / multiple-choice in v0.1.
    Correct answers are stored securely and never exposed during active attempts.
    """

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    topic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType), default=QuestionType.SINGLE_CHOICE, nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty), default=Difficulty.MEDIUM, nullable=False, index=True
    )
    marks: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    status: Mapped[QuestionStatus] = mapped_column(
        Enum(QuestionStatus), default=QuestionStatus.ACTIVE, nullable=False, index=True
    )
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    subject: Mapped[Optional["Subject"]] = relationship("Subject", back_populates="questions")
    topic: Mapped[Optional["Topic"]] = relationship("Topic", back_populates="questions")
    options: Mapped[List["QuestionOption"]] = relationship(
        "QuestionOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.order",
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id} type={self.question_type}>"

    @property
    def correct_option_ids(self) -> List[int]:
        """Return IDs of options marked as correct. Internal use only."""
        return [opt.id for opt in self.options if opt.is_correct]


class QuestionOption(Base):
    """A single answer option belonging to a Question."""

    __tablename__ = "question_options"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    question: Mapped["Question"] = relationship("Question", back_populates="options")

    def __repr__(self) -> str:
        return f"<QuestionOption id={self.id} correct={self.is_correct}>"
