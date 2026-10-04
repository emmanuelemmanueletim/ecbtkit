"""Examination endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ecbtkit.auth.deps import get_current_user, require_examiner
from ecbtkit.core.exceptions import NotFoundError, ValidationError
from ecbtkit.db.base import get_db
from ecbtkit.models.exam import Exam, ExamStatus
from ecbtkit.models.user import User
from ecbtkit.schemas.exam import ExamAdminOut, ExamCreate, ExamOut, ExamUpdate

router = APIRouter(prefix="/exams", tags=["Examinations"])


@router.post("", response_model=ExamAdminOut, status_code=201)
def create_exam(
    payload: ExamCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_examiner),
):
    exam = Exam(
        title=payload.title,
        description=payload.description,
        instructions=payload.instructions,
        subject=payload.subject,
        duration_minutes=payload.duration_minutes,
        available_from=payload.available_from,
        available_until=payload.available_until,
        attempt_limit=payload.attempt_limit,
        question_count=payload.question_count,
        randomize_questions=payload.randomize_questions,
        randomize_options=payload.randomize_options,
        marks_correct=payload.marks_correct,
        marks_wrong=payload.marks_wrong,
        marks_unanswered=payload.marks_unanswered,
        pass_mark=payload.pass_mark,
        result_visibility=payload.result_visibility,
        show_correct_answers=payload.show_correct_answers,
        show_explanations=payload.show_explanations,
        status=ExamStatus.DRAFT,
    )
    if payload.selection_rules:
        exam.selection_rules = payload.selection_rules
    if payload.grading_scale:
        exam.grading_scale = payload.grading_scale

    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.get("", response_model=List[ExamOut])
def list_exams(
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Exam)
    # Candidates only see published
    if user.role.value == "candidate":
        q = q.filter(Exam.status == ExamStatus.PUBLISHED)
    elif status:
        q = q.filter(Exam.status == status)
    return q.order_by(Exam.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{exam_id}", response_model=ExamOut)
def get_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise NotFoundError("Examination", exam_id)
    if user.role.value == "candidate" and exam.status != ExamStatus.PUBLISHED:
        raise NotFoundError("Examination", exam_id)
    return exam


@router.patch("/{exam_id}", response_model=ExamAdminOut)
def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_examiner),
):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise NotFoundError("Examination", exam_id)

    data = payload.model_dump(exclude_unset=True)
    selection = data.pop("selection_rules", None)
    grading = data.pop("grading_scale", None)

    for k, v in data.items():
        setattr(exam, k, v)
    if selection is not None:
        exam.selection_rules = selection
    if grading is not None:
        exam.grading_scale = grading

    db.commit()
    db.refresh(exam)
    return exam


@router.post("/{exam_id}/publish", response_model=ExamAdminOut)
def publish_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_examiner),
):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise NotFoundError("Examination", exam_id)
    if exam.question_count < 1:
        raise ValidationError("Exam must have at least one question configured")
    exam.status = ExamStatus.PUBLISHED
    db.commit()
    db.refresh(exam)
    return exam
