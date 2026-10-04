"""Attempt and answer schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ecbtkit.models.attempt import AttemptStatus
from ecbtkit.schemas.common import ORMModel


class StartAttemptRequest(BaseModel):
    exam_id: int


class AnswerSubmit(BaseModel):
    question_id: int
    selected_option_ids: List[int] = Field(default_factory=list)


class OptionPublic(BaseModel):
    id: int
    text: str
    order: int


class QuestionPublic(BaseModel):
    question_id: int
    text: str
    marks: float
    options: List[OptionPublic]
    selected_option_ids: List[int] = []


class AttemptOut(ORMModel):
    id: int
    exam_id: int
    candidate_id: int
    status: AttemptStatus
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    remaining_seconds: Optional[int] = None
    score: Optional[float] = None
    percentage: Optional[float] = None
    grade: Optional[str] = None
    passed: Optional[bool] = None


class AttemptWithQuestions(AttemptOut):
    questions: List[QuestionPublic] = []


class ResultOut(ORMModel):
    id: int
    attempt_id: int
    exam_id: int
    candidate_id: int
    score: float
    max_score: float
    percentage: float
    grade: Optional[str] = None
    passed: bool
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    time_used_seconds: Optional[int] = None
    submitted_at: Optional[datetime] = None
    # breakdown only included when visibility permits
    breakdown: Optional[List[Dict[str, Any]]] = None
