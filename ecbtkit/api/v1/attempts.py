"""Attempt, answer, and result endpoints."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from ecbtkit.auth.deps import get_current_user, require_candidate, require_examiner
from ecbtkit.core.exceptions import NotFoundError, ValidationError
from ecbtkit.db.base import get_db
from ecbtkit.engine.attempt_service import AttemptService
from ecbtkit.models.attempt import Attempt
from ecbtkit.models.candidate import Candidate
from ecbtkit.models.result import Result
from ecbtkit.models.user import User
from ecbtkit.schemas.attempt import (
    AnswerSubmit,
    AttemptOut,
    AttemptWithQuestions,
    QuestionPublic,
    ResultOut,
    StartAttemptRequest,
)

router = APIRouter(tags=["Attempts"])


def _get_candidate_id(user: User, db: Session) -> int:
    if user.candidate_profile:
        return user.candidate_profile.id
    # Fallback lookup
    cand = db.query(Candidate).filter(Candidate.user_id == user.id).first()
    if not cand:
        raise ValidationError("No candidate profile linked to this user")
    return cand.id


@router.post("/exams/{exam_id}/start", response_model=AttemptWithQuestions, status_code=201)
def start_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    candidate_id = _get_candidate_id(user, db)
    service = AttemptService(db)
    attempt = service.start_attempt(exam_id, candidate_id)
    questions = service.get_attempt_questions_for_candidate(attempt.id, candidate_id)

    out = AttemptWithQuestions.model_validate(attempt)
    out.remaining_seconds = attempt.remaining_seconds()
    out.questions = [QuestionPublic(**q) for q in questions]
    return out


@router.get("/attempts/{attempt_id}", response_model=AttemptWithQuestions)
def get_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    candidate_id = _get_candidate_id(user, db)
    service = AttemptService(db)
    # Will raise if not active / not owned
    questions = service.get_attempt_questions_for_candidate(attempt_id, candidate_id)
    attempt = db.get(Attempt, attempt_id)

    out = AttemptWithQuestions.model_validate(attempt)
    out.remaining_seconds = attempt.remaining_seconds()
    out.questions = [QuestionPublic(**q) for q in questions]
    return out


@router.post("/attempts/{attempt_id}/answers", response_model=dict)
def submit_answer(
    attempt_id: int,
    payload: AnswerSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    candidate_id = _get_candidate_id(user, db)
    service = AttemptService(db)
    answer = service.submit_answer(
        attempt_id,
        payload.question_id,
        payload.selected_option_ids,
        candidate_id=candidate_id,
    )
    return {
        "question_id": answer.question_id,
        "selected_option_ids": answer.selected_ids,
        "answered_at": answer.answered_at.isoformat() if answer.answered_at else None,
    }


@router.delete("/attempts/{attempt_id}/answers/{question_id}", status_code=204)
def clear_answer(
    attempt_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    candidate_id = _get_candidate_id(user, db)
    service = AttemptService(db)
    service.clear_answer(attempt_id, question_id, candidate_id=candidate_id)
    return None


@router.post("/attempts/{attempt_id}/submit", response_model=ResultOut)
def submit_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_candidate),
):
    candidate_id = _get_candidate_id(user, db)
    service = AttemptService(db)
    result = service.submit_attempt(attempt_id, candidate_id=candidate_id)

    # Apply visibility rules
    exam = result.exam
    out = ResultOut.model_validate(result)
    if exam.result_visibility in ("score_only",):
        out.correct_count = 0
        out.incorrect_count = 0
        out.unanswered_count = 0
        out.breakdown = None
    elif exam.result_visibility == "score_percentage":
        out.breakdown = None
    elif exam.result_visibility in ("correct_wrong_count", "detailed_review", "full"):
        if exam.result_visibility == "full" or exam.show_correct_answers:
            out.breakdown = result.breakdown.get("items") if isinstance(result.breakdown, dict) else result.breakdown
        else:
            out.breakdown = None
    return out


@router.get("/results/{result_id}", response_model=ResultOut)
def get_result(
    result_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = (
        db.query(Result)
        .options(selectinload(Result.exam))
        .filter(Result.id == result_id)
        .first()
    )
    if not result:
        raise NotFoundError("Result", result_id)

    # Candidates can only see their own
    if user.role.value == "candidate":
        cand_id = _get_candidate_id(user, db)
        if result.candidate_id != cand_id:
            raise NotFoundError("Result", result_id)

    out = ResultOut.model_validate(result)
    exam = result.exam
    if exam and exam.result_visibility in ("score_only", "score_percentage"):
        out.breakdown = None
    return out


@router.get("/exams/{exam_id}/results", response_model=List[ResultOut])
def list_exam_results(
    exam_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_examiner),
):
    results = (
        db.query(Result)
        .filter(Result.exam_id == exam_id)
        .order_by(Result.created_at.desc())
        .all()
    )
    return results
