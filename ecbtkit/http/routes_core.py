"""Health, questions, exams, attempts routes (Starlette)."""

from __future__ import annotations

from typing import Any, Dict

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
from ecbtkit.models.question import Difficulty, Question, QuestionOption, QuestionStatus, QuestionType, Subject, Topic
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
    try:
        eng = get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return _ok({"status": "ok", "database": "connected", "backend": "sql"})
    except Exception as exc:
        return APIResponse(
            {"status": "error", "database": "unavailable", "backend": "sql"},
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
        name = name.strip()
        if not name or len(name) > 150:
            raise ValidationError("name must be between 1 and 150 characters")
        if db.query(Subject).filter(Subject.name == name).first():
            raise ValidationError(f"Subject '{name}' already exists")
        sub = Subject(name=name, code=body.get("code"), description=body.get("description"))
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return _ok({"id": sub.id, "name": sub.name, "code": sub.code}, 201)
    except ECBTError as e:
        return error_response(e)
    except Exception as exc:
        db.rollback()
        return internal_error_response(get_settings().debug, str(exc))
    finally:
        db.close()


async def list_subjects(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        require_roles(user, UserRole.EXAMINER, UserRole.ADMINISTRATOR)
        rows = db.query(Subject).order_by(Subject.name).all()
        return _ok([{"id": s.id, "name": s.name, "code": s.code} for s in rows])
    except ECBTError as exc:
        return error_response(exc)
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
        name = name.strip()
        if not name or len(name) > 150:
            raise ValidationError("name must be between 1 and 150 characters")
        try:
            subject_id = int(subject_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("subject_id must be an integer") from exc
        if not db.get(Subject, subject_id):
            raise NotFoundError("Subject", subject_id)
        topic = Topic(name=name, subject_id=subject_id, code=body.get("code"))
        db.add(topic)
        db.commit()
        db.refresh(topic)
        return _ok({"id": topic.id, "name": topic.name, "subject_id": topic.subject_id}, 201)
    except ECBTError as e:
        return error_response(e)
    except Exception as exc:
        db.rollback()
        return internal_error_response(get_settings().debug, str(exc))
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
        if not text_q or not isinstance(options, list) or len(options) < 2:
            raise ValidationError("text and at least 2 options are required")
        if any(not isinstance(option, dict) or not option.get("text") for option in options):
            raise ValidationError("Every option must include text")
        if any(len(option["text"]) > 10_000 for option in options) or len(text_q) > 50_000:
            raise ValidationError("Question text and option text exceed the maximum size")
        if not any(o.get("is_correct") is True for o in options):
            raise ValidationError("At least one option must be is_correct: true")
        question_type = body.get("question_type", "single_choice")
        if question_type not in ("single_choice", "multiple_choice", "true_false"):
            raise ValidationError("Unsupported question_type")
        correct_count = sum(bool(o.get("is_correct")) for o in options)
        if question_type != "multiple_choice" and correct_count != 1:
            raise ValidationError("Single choice and true/false questions require exactly one correct option")
        if float(body.get("marks", 1.0)) <= 0:
            raise ValidationError("Question marks must be positive")
        q = Question(
            text=text_q,
            subject_id=body.get("subject_id"),
            topic_id=body.get("topic_id"),
            explanation=body.get("explanation"),
            marks=float(body.get("marks", 1.0)),
            question_type=QuestionType(question_type),
            difficulty=Difficulty(body.get("difficulty", "medium")),
            tags=body.get("tags"),
            status=QuestionStatus.ACTIVE,
        )
        if q.subject_id is not None and not db.get(Subject, q.subject_id):
            raise ValidationError("subject_id does not reference a subject")
        if q.topic_id is not None:
            topic = db.get(Topic, q.topic_id)
            if not topic:
                raise ValidationError("topic_id does not reference a topic")
            if q.subject_id is not None and topic.subject_id != q.subject_id:
                raise ValidationError("topic_id does not belong to subject_id")
        db.add(q)
        try:
            db.flush()
            for i, opt in enumerate(options):
                db.add(QuestionOption(
                    question_id=q.id,
                    text=opt["text"],
                    is_correct=bool(opt.get("is_correct")),
                    order=opt.get("order", i),
                ))
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.refresh(q)
        return _ok({"id": q.id, "text": q.text}, 201)
    except ECBTError as e:
        return error_response(e)
    except Exception as exc:
        db.rollback()
        return internal_error_response(get_settings().debug, str(exc))
    finally:
        db.close()


async def list_questions(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        require_roles(user, UserRole.EXAMINER, UserRole.ADMINISTRATOR)
        q = db.query(Question).options(selectinload(Question.options))
        subject_id = request.query_params.get("subject_id")
        if request.query_params.get("difficulty"):
            q = q.filter(Question.difficulty == request.query_params["difficulty"])
        if request.query_params.get("status"):
            q = q.filter(Question.status == request.query_params["status"])
        if subject_id:
            q = q.filter(Question.subject_id == int(subject_id))
        offset = max(0, int(request.query_params.get("skip", "0")))
        limit = min(200, max(1, int(request.query_params.get("limit", "50"))))
        rows = q.offset(offset).limit(limit).all()
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
    except (ValueError, TypeError) as exc:
        return error_response(ValidationError(f"Invalid query parameter: {exc}"))
    except Exception as exc:
        return internal_error_response(get_settings().debug, str(exc))
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
        title = title.strip()
        if not title or len(title) > 255:
            raise ValidationError("title must be between 1 and 255 characters")
        duration = int(body.get("duration_minutes", 60))
        question_count = int(body.get("question_count", 10))
        attempt_limit = int(body.get("attempt_limit", 1))
        if duration < 1 or question_count < 1 or attempt_limit < 0:
            raise ValidationError("duration_minutes and question_count must be positive; attempt_limit must be non-negative")
        selection_rules = body.get("selection_rules") or {}
        if not isinstance(selection_rules, dict):
            raise ValidationError("selection_rules must be an object")
        for quota_key in ("topics", "difficulty"):
            if quota_key in selection_rules and not isinstance(selection_rules[quota_key], dict):
                raise ValidationError(f"selection_rules.{quota_key} must be an object")
        if "topics" in selection_rules and "difficulty" in selection_rules:
            raise ValidationError("Specify topic quotas or difficulty quotas, not both")
        if "tags" in selection_rules and (not isinstance(selection_rules["tags"], list) or any(not isinstance(tag, str) or not tag.strip() for tag in selection_rules["tags"])):
            raise ValidationError("selection_rules.tags must be a list of non-empty strings")
        for key in ("topics", "difficulty"):
            quotas = selection_rules.get(key, {})
            if any(type(value) is not int or value < 0 for value in quotas.values()):
                raise ValidationError(f"{key} quota values must be non-negative integers")
            if sum(quotas.values()) > question_count:
                raise ValidationError(f"{key} quotas cannot exceed question_count")
        marks_correct = float(body.get("marks_correct", 1.0))
        marks_wrong = float(body.get("marks_wrong", 0.0))
        marks_unanswered = float(body.get("marks_unanswered", 0.0))
        pass_mark = float(body.get("pass_mark", 40.0))
        if marks_correct <= 0 or marks_wrong > 0 or marks_unanswered < 0 or not 0 <= pass_mark <= 100:
            raise ValidationError("Scoring must use positive correct marks, non-positive wrong marks, non-negative unanswered marks, and pass_mark from 0 to 100")
        if body.get("result_visibility", "score_percentage") not in {"score_only", "score_percentage", "correct_wrong_count", "detailed_review", "full"}:
            raise ValidationError("Invalid result_visibility")
        if body.get("available_from"):
            from datetime import datetime, timezone
            parsed = datetime.fromisoformat(body["available_from"].replace("Z", "+00:00"))
            body["available_from"] = parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed
        if body.get("available_until"):
            from datetime import datetime, timezone
            parsed = datetime.fromisoformat(body["available_until"].replace("Z", "+00:00"))
            body["available_until"] = parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed
        if body.get("available_from") and body.get("available_until") and body["available_from"] >= body["available_until"]:
            raise ValidationError("available_until must be after available_from")
        exam = Exam(
            title=title,
            description=body.get("description"),
            subject=body.get("subject"),
            duration_minutes=duration,
            question_count=question_count,
            randomize_questions=bool(body.get("randomize_questions", True)),
            randomize_options=bool(body.get("randomize_options", True)),
            marks_correct=marks_correct,
            marks_wrong=marks_wrong,
            marks_unanswered=marks_unanswered,
            pass_mark=pass_mark,
            attempt_limit=int(body.get("attempt_limit", 1)),
            status=ExamStatus.DRAFT,
        )
        if selection_rules:
            exam.selection_rules = selection_rules
        if body.get("grading_scale") is not None:
            if not isinstance(body["grading_scale"], list):
                raise ValidationError("grading_scale must be an array")
            exam.grading_scale = body["grading_scale"]
        exam.instructions = body.get("instructions")
        exam.result_visibility = body.get("result_visibility", "score_percentage")
        exam.show_correct_answers = bool(body.get("show_correct_answers", False))
        exam.show_explanations = bool(body.get("show_explanations", False))
        exam.available_from = body.get("available_from")
        exam.available_until = body.get("available_until")
        exam.marks_unanswered = marks_unanswered
        db.add(exam)
        db.commit()
        db.refresh(exam)
        return _ok({"id": exam.id, "title": exam.title, "status": exam.status.value}, 201)
    except ECBTError as e:
        return error_response(e)
    except (ValueError, TypeError) as exc:
        return error_response(ValidationError(f"Invalid exam data: {exc}"))
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
    except Exception as exc:
        return internal_error_response(get_settings().debug, str(exc))
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
        if exam.question_count < 1:
            raise ValidationError("Exam must require at least one question")
        exam.status = ExamStatus.PUBLISHED
        db.commit()
        return _ok({"id": exam.id, "status": exam.status.value})
    except ECBTError as e:
        return error_response(e)
    except Exception as exc:
        return internal_error_response(get_settings().debug, str(exc))
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
    except Exception as exc:
        return internal_error_response(get_settings().debug, str(exc))
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
    except Exception as exc:
        db.rollback()
        return internal_error_response(get_settings().debug, str(exc))
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
    except Exception as exc:
        db.rollback()
        return internal_error_response(get_settings().debug, str(exc))
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
