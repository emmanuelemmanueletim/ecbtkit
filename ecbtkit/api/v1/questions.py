"""Question bank endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload

from ecbtkit.auth.deps import require_examiner
from ecbtkit.core.exceptions import NotFoundError, ValidationError
from ecbtkit.db.base import get_db
from ecbtkit.models.question import Question, QuestionOption, QuestionStatus, Subject, Topic
from ecbtkit.models.user import User
from ecbtkit.schemas.question import (
    QuestionAdminOut,
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
    SubjectCreate,
    SubjectOut,
    TopicCreate,
    TopicOut,
)

router = APIRouter(tags=["Questions"])


# ---- Subjects -----------------------------------------------------------

@router.post("/subjects", response_model=SubjectOut, status_code=201)
def create_subject(
    payload: SubjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_examiner),
):
    existing = db.query(Subject).filter(Subject.name == payload.name).first()
    if existing:
        raise ValidationError(f"Subject '{payload.name}' already exists")
    sub = Subject(name=payload.name, code=payload.code, description=payload.description)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.get("/subjects", response_model=List[SubjectOut])
def list_subjects(db: Session = Depends(get_db)):
    return db.query(Subject).order_by(Subject.name).all()


# ---- Topics -------------------------------------------------------------

@router.post("/topics", response_model=TopicOut, status_code=201)
def create_topic(
    payload: TopicCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_examiner),
):
    sub = db.get(Subject, payload.subject_id)
    if not sub:
        raise NotFoundError("Subject", payload.subject_id)
    topic = Topic(
        name=payload.name,
        subject_id=payload.subject_id,
        code=payload.code,
        description=payload.description,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


@router.get("/topics", response_model=List[TopicOut])
def list_topics(
    subject_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Topic)
    if subject_id:
        q = q.filter(Topic.subject_id == subject_id)
    return q.order_by(Topic.name).all()


# ---- Questions ----------------------------------------------------------

@router.post("/questions", response_model=QuestionAdminOut, status_code=201)
def create_question(
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_examiner),
):
    if len(payload.options) < 2:
        raise ValidationError("At least two options are required")
    correct_count = sum(1 for o in payload.options if o.is_correct)
    if correct_count < 1:
        raise ValidationError("At least one option must be marked correct")

    q = Question(
        text=payload.text,
        subject_id=payload.subject_id,
        topic_id=payload.topic_id,
        question_type=payload.question_type,
        explanation=payload.explanation,
        difficulty=payload.difficulty,
        marks=payload.marks,
        tags=payload.tags,
        status=QuestionStatus.ACTIVE,
    )
    db.add(q)
    db.flush()

    for i, opt in enumerate(payload.options):
        db.add(
            QuestionOption(
                question_id=q.id,
                text=opt.text,
                is_correct=opt.is_correct,
                order=opt.order if opt.order else i,
            )
        )

    db.commit()
    db.refresh(q)
    # reload options
    q = (
        db.query(Question)
        .options(selectinload(Question.options))
        .filter(Question.id == q.id)
        .one()
    )
    return q


@router.get("/questions", response_model=List[QuestionAdminOut])
def list_questions(
    subject_id: Optional[int] = None,
    topic_id: Optional[int] = None,
    difficulty: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_examiner),
):
    q = db.query(Question).options(selectinload(Question.options))
    if subject_id:
        q = q.filter(Question.subject_id == subject_id)
    if topic_id:
        q = q.filter(Question.topic_id == topic_id)
    if difficulty:
        q = q.filter(Question.difficulty == difficulty)
    if status:
        q = q.filter(Question.status == status)
    return q.offset(skip).limit(limit).all()


@router.get("/questions/{question_id}", response_model=QuestionAdminOut)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_examiner),
):
    q = (
        db.query(Question)
        .options(selectinload(Question.options))
        .filter(Question.id == question_id)
        .first()
    )
    if not q:
        raise NotFoundError("Question", question_id)
    return q


@router.patch("/questions/{question_id}", response_model=QuestionAdminOut)
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_examiner),
):
    q = db.get(Question, question_id)
    if not q:
        raise NotFoundError("Question", question_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(q, k, v)
    db.commit()
    db.refresh(q)
    return q
