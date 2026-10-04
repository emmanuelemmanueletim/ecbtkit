"""Health, questions, exams, attempts routes (Starlette)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from starlette.requests import Request
from starlette.routing import Route
from sqlalchemy.orm import selectinload

from ecbtkit.core.config import get_settings
from ecbtkit.core.exceptions import ECBTError, NotFoundError, ValidationError
from ecbtkit.db.base import get_engine
from ecbtkit.engine.attempt_service import AttemptService
from ecbtkit.http.deps import get_current_user, open_db, require_roles
from ecbtkit.http.responses import APIResponse, error_response, internal_error_response
from ecbtkit.models.candidate import Candidate
from ecbtkit.models.exam import Exam, ExamStatus
from ecbtkit.models.question import Question, QuestionOption, QuestionStatus, Subject, Topic
from ecbtkit.models.result import Result
from ecbtkit.models.user import UserRole
from sqlalchemy import text


async def _json(request: Request) -> Dict[str, Any]:
    try:
        return await request.json()
    except Exception:
        raise ValidationError("Request body must be valid JSON")


def _ok(data: Any, status: int = 200) -> APIResponse:
    return APIResponse(data, status_code=status)


# ---- Health ---------------------------------------------------------------

async def health(request: Request):
    return _ok({"status": "ok", "service": "ecbtkit", "version": get_settings().app_version})


async def health_db(request: Request):
    settings = get_settings()
    if settings.resolved_backend == "mongo":
        from ecbtkit.adapters.mongo import mongo_health
        return _ok(mongo_health())
    try:
        eng = get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return _ok({"status": "ok", "database": "connected", "backend": "sql"})
    except Exception as exc:
        return APIResponse(
            {"status": "error", "database": str(exc), "backend": "sql"},
            status_code=503,
        )


# ---- Subjects / Topics / Questions ----------------------------------------

async def create_subject(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        require_roles(user, UserRole.EXAMINER, UserRole.ADMINISTRATOR)
        body = await _json(request)
        name = body.get("name")
        if not name:
            raise ValidationError("name is required")
        if db.query(Subject).filter(Subject.name == name).first():
            raise ValidationError(f"Subject '{name}' already exists")
        sub = Subject(name=name, code=body.get("code"), description=body.get("description"))
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return _ok({"id": sub.id, "name": sub.name, "code": sub.code}, 201)
    except ECBTError as e:
        return error_response(e)
    finally:
        db.close()


async def list_subjects(request: Request):
    db = open_db()
    try:
        rows = db.query(Subject).order_by(Subject.name).all()
        return _ok([{"id": s.id, "name": s.name, "code": s.code} for s in rows])
    finally:
        db.close()


async def create_topic(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        require_roles(user, UserRole.EXAMINER, UserRole.ADMINISTRATOR)
        body = await _json(request)
        name = body.get("name")
        subject_id = body.get("subject_id")
        if not name or not subject_id:
            raise ValidationError("name and subject_id are required")
        if not db.get(Subject, subject_id):
            raise NotFoundError("Subject", subject_id)
        topic = Topic(name=name, subject_id=subject_id, code=body.get("code"))
        db.add(topic)
        db.commit()
        db.refresh(topic)
        return _ok({"id": topic.id, "name": topic.name, "subject_id": topic.subject_id}, 201)
    except ECBTError as e:
        return error_response(e)
    finally:
        db.close()


async def create_question(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        require_roles(user, UserRole.EXAMINER, UserRole.ADMINISTRATOR)
        body = await _json(request)
        text_q = body.get("text")
        options = body.get("options") or []
        if not text_q or len(options) < 2:
            raise ValidationError("text and at least 2 options are required")
        if not any(o.get("is_correct") for o in options):
            raise ValidationError("At least one option must be is_correct: true")
        q = Question(
            text=text_q,
            subject_id=body.get("subject_id"),
            topic_id=body.get("topic_id"),
            explanation=body.get("explanation"),
            marks=float(body.get("marks", 1.0)),
            status=QuestionStatus.ACTIVE,
        )
        db.add(q)
        db.flush()
        for i, opt in enumerate(options):
            db.add(QuestionOption(
                question_id=q.id,
                text=opt["text"],
                is_correct=bool(opt.get("is_correct")),
                order=opt.get("order", i),
            ))
        db.commit()
        db.refresh(q)
        return _ok({"id": q.id, "text": q.text}, 201)
    except ECBTError as e:
        return error_response(e)
    finally:
        db.close()


async def list_questions(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        require_roles(user, UserRole.EXAMINER, UserRole.ADMINISTRATOR)
        q = db.query(Question).options(selectinload(Question.options))
        subject_id = request.query_params.get("subject_id")
        if subject_id:
            q = q.filter(Question.subject_id == int(subject_id))
        rows = q.limit(100).all()
        return _ok([
            {
                "id": r.id,
                "text": r.text,
                "subject_id": r.subject_id,
                "topic_id": r.topic_id,
                "options": [
                    {"id": o.id, "text": o.text, "is_correct": o.is_correct, "order": o.order}
                    for o in r.options
                ],
            }
            for r in rows
        ])
    except ECBTError as e:
        return error_response(e)
    finally:
        db.close()


# ---- Exams ----------------------------------------------------------------

async def create_exam(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        require_roles(user, UserRole.EXAMINER, UserRole.ADMINISTRATOR)
        body = await _json(request)
        title = body.get("title")
        if not title:
            raise ValidationError("title is required")
        exam = Exam(
            title=title,
            description=body.get("description"),
            subject=body.get("subject"),
            duration_minutes=int(body.get("duration_minutes", 60)),
            question_count=int(body.get("question_count", 10)),
            randomize_questions=bool(body.get("randomize_questions", True)),
            randomize_options=bool(body.get("randomize_options", True)),
            marks_correct=float(body.get("marks_correct", 1.0)),
            marks_wrong=float(body.get("marks_wrong", 0.0)),
            pass_mark=float(body.get("pass_mark", 40.0)),
            attempt_limit=int(body.get("attempt_limit", 1)),
            status=ExamStatus.DRAFT,
        )
        if body.get("selection_rules"):
            exam.selection_rules = body["selection_rules"]
        db.add(exam)
        db.commit()
        db.refresh(exam)
        return _ok({"id": exam.id, "title": exam.title, "status": exam.status.value}, 201)
    except ECBTError as e:
        return error_response(e)
    finally:
        db.close()


async def list_exams(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        q = db.query(Exam)
        if user.role == UserRole.CANDIDATE:
            q = q.filter(Exam.status == ExamStatus.PUBLISHED)
        rows = q.order_by(Exam.created_at.desc()).limit(50).all()
        return _ok([
            {
                "id": e.id,
                "title": e.title,
                "duration_minutes": e.duration_minutes,
                "question_count": e.question_count,
                "status": e.status.value,
                "pass_mark": e.pass_mark,
            }
            for e in rows
        ])
    except ECBTError as e:
        return error_response(e)
    finally:
        db.close()


async def publish_exam(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        require_roles(user, UserRole.EXAMINER, UserRole.ADMINISTRATOR)
        exam_id = int(request.path_params["exam_id"])
        exam = db.get(Exam, exam_id)
        if not exam:
            raise NotFoundError("Examination", exam_id)
        exam.status = ExamStatus.PUBLISHED
        db.commit()
        return _ok({"id": exam.id, "status": exam.status.value})
    except ECBTError as e:
        return error_response(e)
    finally:
        db.close()


# ---- Attempts -------------------------------------------------------------

def _candidate_id(user, db) -> int:
    if user.candidate_profile:
        return user.candidate_profile.id
    cand = db.query(Candidate).filter(Candidate.user_id == user.id).first()
    if not cand:
        raise ValidationError("No candidate profile linked to this user")
    return cand.id


async def start_exam(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        require_roles(user, UserRole.CANDIDATE, UserRole.ADMINISTRATOR)
        exam_id = int(request.path_params["exam_id"])
        cand_id = _candidate_id(user, db)
        svc = AttemptService(db)
        attempt = svc.start_attempt(exam_id, cand_id)
        questions = svc.get_attempt_questions_for_candidate(attempt.id, cand_id)
        return _ok({
            "id": attempt.id,
            "exam_id": attempt.exam_id,
            "status": attempt.status.value,
            "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
            "expires_at": attempt.expires_at.isoformat() if attempt.expires_at else None,
            "remaining_seconds": attempt.remaining_seconds(),
            "questions": questions,
        }, 201)
    except ECBTError as e:
        return error_response(e)
    finally:
        db.close()


async def submit_answer(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        require_roles(user, UserRole.CANDIDATE, UserRole.ADMINISTRATOR)
        attempt_id = int(request.path_params["attempt_id"])
        body = await _json(request)
        qid = body.get("question_id")
        selected = body.get("selected_option_ids") or []
        if not qid:
            raise ValidationError("question_id is required")
        cand_id = _candidate_id(user, db)
        answer = AttemptService(db).submit_answer(
            attempt_id, int(qid), [int(x) for x in selected], candidate_id=cand_id
        )
        return _ok({
            "question_id": answer.question_id,
            "selected_option_ids": answer.selected_ids,
        })
    except ECBTError as e:
        return error_response(e)
    finally:
        db.close()


async def submit_attempt(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        require_roles(user, UserRole.CANDIDATE, UserRole.ADMINISTRATOR)
        attempt_id = int(request.path_params["attempt_id"])
        cand_id = _candidate_id(user, db)
        result = AttemptService(db).submit_attempt(attempt_id, candidate_id=cand_id)
        return _ok({
            "id": result.id,
            "score": result.score,
            "max_score": result.max_score,
            "percentage": result.percentage,
            "grade": result.grade,
            "passed": result.passed,
            "correct_count": result.correct_count,
            "incorrect_count": result.incorrect_count,
            "unanswered_count": result.unanswered_count,
        })
    except ECBTError as e:
        return error_response(e)
    finally:
        db.close()


core_routes = [
    Route("/health", health, methods=["GET"]),
    Route("/health/database", health_db, methods=["GET"]),
    Route("/subjects", create_subject, methods=["POST"]),
    Route("/subjects", list_subjects, methods=["GET"]),
    Route("/topics", create_topic, methods=["POST"]),
    Route("/questions", create_question, methods=["POST"]),
    Route("/questions", list_questions, methods=["GET"]),
    Route("/exams", create_exam, methods=["POST"]),
    Route("/exams", list_exams, methods=["GET"]),
    Route("/exams/{exam_id:int}/publish", publish_exam, methods=["POST"]),
    Route("/exams/{exam_id:int}/start", start_exam, methods=["POST"]),
    Route("/attempts/{attempt_id:int}/answers", submit_answer, methods=["POST"]),
    Route("/attempts/{attempt_id:int}/submit", submit_attempt, methods=["POST"]),
]
