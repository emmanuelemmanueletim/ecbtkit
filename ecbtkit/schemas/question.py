"""Question bank schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from ecbtkit.models.question import Difficulty, QuestionStatus, QuestionType
from ecbtkit.schemas.common import ORMModel


class OptionCreate(BaseModel):
    text: str
    is_correct: bool = False
    order: int = 0


class OptionOut(ORMModel):
    id: int
    text: str
    order: int
    # is_correct deliberately omitted for candidate-facing responses


class OptionAdminOut(OptionOut):
    is_correct: bool


class QuestionCreate(BaseModel):
    text: str
    subject_id: Optional[int] = None
    topic_id: Optional[int] = None
    question_type: QuestionType = QuestionType.SINGLE_CHOICE
    explanation: Optional[str] = None
    difficulty: Difficulty = Difficulty.MEDIUM
    marks: float = 1.0
    tags: Optional[str] = None
    options: List[OptionCreate] = Field(min_length=2)


class QuestionUpdate(BaseModel):
    text: Optional[str] = None
    subject_id: Optional[int] = None
    topic_id: Optional[int] = None
    explanation: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    marks: Optional[float] = None
    tags: Optional[str] = None
    status: Optional[QuestionStatus] = None


class QuestionOut(ORMModel):
    id: int
    text: str
    subject_id: Optional[int] = None
    topic_id: Optional[int] = None
    question_type: QuestionType
    difficulty: Difficulty
    marks: float
    status: QuestionStatus
    tags: Optional[str] = None
    options: List[OptionOut] = []
    created_at: datetime


class QuestionAdminOut(QuestionOut):
    explanation: Optional[str] = None
    options: List[OptionAdminOut] = []


class SubjectCreate(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None


class SubjectOut(ORMModel):
    id: int
    name: str
    code: Optional[str] = None
    description: Optional[str] = None


class TopicCreate(BaseModel):
    name: str
    subject_id: int
    code: Optional[str] = None
    description: Optional[str] = None


class TopicOut(ORMModel):
    id: int
    name: str
    subject_id: int
    code: Optional[str] = None
