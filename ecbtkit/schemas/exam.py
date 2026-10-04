"""Examination schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ecbtkit.models.exam import ExamStatus
from ecbtkit.schemas.common import ORMModel


class ExamCreate(BaseModel):
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    subject: Optional[str] = None
    duration_minutes: int = Field(default=60, ge=1)
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None
    attempt_limit: int = Field(default=1, ge=0)
    question_count: int = Field(default=50, ge=1)
    randomize_questions: bool = True
    randomize_options: bool = True
    selection_rules: Optional[Dict[str, Any]] = None
    marks_correct: float = 1.0
    marks_wrong: float = 0.0
    marks_unanswered: float = 0.0
    pass_mark: float = Field(default=40.0, ge=0, le=100)
    grading_scale: Optional[List[Dict[str, Any]]] = None
    result_visibility: str = "score_percentage"
    show_correct_answers: bool = False
    show_explanations: bool = False


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, ge=1)
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None
    attempt_limit: Optional[int] = Field(default=None, ge=0)
    question_count: Optional[int] = Field(default=None, ge=1)
    randomize_questions: Optional[bool] = None
    randomize_options: Optional[bool] = None
    selection_rules: Optional[Dict[str, Any]] = None
    marks_correct: Optional[float] = None
    marks_wrong: Optional[float] = None
    marks_unanswered: Optional[float] = None
    pass_mark: Optional[float] = None
    grading_scale: Optional[List[Dict[str, Any]]] = None
    result_visibility: Optional[str] = None
    show_correct_answers: Optional[bool] = None
    show_explanations: Optional[bool] = None
    status: Optional[ExamStatus] = None


class ExamOut(ORMModel):
    id: int
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    subject: Optional[str] = None
    duration_minutes: int
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None
    attempt_limit: int
    question_count: int
    randomize_questions: bool
    randomize_options: bool
    pass_mark: float
    status: ExamStatus
    result_visibility: str
    created_at: datetime


class ExamAdminOut(ExamOut):
    selection_rules: Optional[Dict[str, Any]] = None
    marks_correct: float
    marks_wrong: float
    marks_unanswered: float
    grading_scale: Optional[List[Dict[str, Any]]] = None
    show_correct_answers: bool
    show_explanations: bool
