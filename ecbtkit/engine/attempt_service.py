"""
Examination Attempt Service — the heart of the lifecycle.

Handles:
- starting an attempt (selection + randomization + timer)
- answering questions
- submitting / auto-expiring
- marking and result generation
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError as SQLIntegrityError
from sqlalchemy.orm import Session, selectinload

from ecbtkit.core.exceptions import (
    AttemptAlreadySubmittedError,
    AttemptLimitExceededError,
    AttemptNotActiveError,
    AttemptNotFoundError,
    ExamExpiredError,
    ExamNotAvailableError,
    ExamNotFoundError,
    ExamNotPublishedError,
    InvalidAttemptStateError,
    InvalidSelectionRulesError,
    QuestionNotInAttemptError,
)
from ecbtkit.engine.marking import MarkingEngine
from ecbtkit.engine.randomization import build_assigned_payload, make_seed
from ecbtkit.engine.selection import QuestionSelector
from ecbtkit.models.attempt import Answer, Attempt, AttemptStatus
from ecbtkit.models.exam import Exam, ExamStatus
from ecbtkit.models.question import Question
from ecbtkit.models.result import Result


class AttemptService:
    """Orchestrates the full examination attempt lifecycle."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    def start_attempt(
        self,
        exam_id: int,
        candidate_id: int,
        *,
        force_seed: Optional[str] = None,
    ) -> Attempt:
        """
        Create and activate a new attempt for the candidate.

        Steps:
        1. Validate exam availability & attempt limit
        2. Select questions according to rules
        3. Randomize (deterministically)
        4. Set server-side timer
        5. Persist attempt in ACTIVE state
        """
        exam = self.db.get(Exam, exam_id)
        if not exam:
            raise ExamNotFoundError(exam_id)
        if exam.status != ExamStatus.PUBLISHED:
            raise ExamNotPublishedError()
        if not exam.is_available():
            raise ExamNotAvailableError()

        # Lock the exam row on databases that support row-level locking.
        # The unique partial index below remains the final concurrency guard.
        if self.db.bind and self.db.bind.dialect.name != "sqlite":
            self.db.query(Exam).filter(Exam.id == exam_id).with_for_update().one()

        active = (
            self.db.query(Attempt)
            .filter(
                Attempt.exam_id == exam_id,
                Attempt.candidate_id == candidate_id,
                Attempt.status == AttemptStatus.ACTIVE,
            )
            .first()
        )
        if active:
            if active.is_expired():
                self._expire_attempt(active)
            else:
                return active

        # Attempt limit
        if exam.attempt_limit > 0:
            existing_count = (
                self.db.query(Attempt)
                .filter(
                    Attempt.exam_id == exam_id,
                    Attempt.candidate_id == candidate_id,
                    Attempt.status.in_(
                        [AttemptStatus.ACTIVE, AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED]
                    ),
                )
                .count()
            )
            if existing_count >= exam.attempt_limit:
                raise AttemptLimitExceededError()

        # Selection
        rules = exam.selection_rules or {}
        selector = QuestionSelector(self.db, seed=force_seed)
        try:
            questions = selector.select(
                total=exam.question_count,
                subject=exam.subject or rules.get("subject"),
                topics=rules.get("topics"),
                difficulty=rules.get("difficulty"),
                tags=rules.get("tags"),
            )
        except ValueError as exc:
            raise InvalidSelectionRulesError(str(exc)) from exc

        # Create attempt first to get an ID for the seed
        now = datetime.utcnow()
        attempt = Attempt(
            exam_id=exam_id,
            candidate_id=candidate_id,
            status=AttemptStatus.CREATED,
            started_at=now,
            expires_at=now + timedelta(minutes=exam.duration_minutes),
        )
        self.db.add(attempt)
        try:
            self.db.flush()  # obtain attempt.id
        except SQLIntegrityError:
            self.db.rollback()
            existing = (
                self.db.query(Attempt)
                .filter(
                    Attempt.exam_id == exam_id,
                    Attempt.candidate_id == candidate_id,
                    Attempt.status == AttemptStatus.ACTIVE,
                )
                .first()
            )
            if existing:
                return existing
            raise

        seed = force_seed or make_seed(exam_id, candidate_id, attempt.id)
        payload = build_assigned_payload(
            questions,
            seed=seed,
            randomize_questions=exam.randomize_questions,
            randomize_options=exam.randomize_options,
        )

        attempt.assigned_questions = payload
        attempt.randomization_seed = seed
        attempt.status = AttemptStatus.ACTIVE

        try:
            self.db.commit()
        except SQLIntegrityError:
            self.db.rollback()
            existing = (
                self.db.query(Attempt)
                .filter(
                    Attempt.exam_id == exam_id,
                    Attempt.candidate_id == candidate_id,
                    Attempt.status == AttemptStatus.ACTIVE,
                )
                .first()
            )
            if existing:
                return existing
            raise
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(attempt)
        return attempt

    # ------------------------------------------------------------------
    # Answer
    # ------------------------------------------------------------------

    def submit_answer(
        self,
        attempt_id: int,
        question_id: int,
        selected_option_ids: List[int],
        *,
        candidate_id: Optional[int] = None,
    ) -> Answer:
        """
        Record or update an answer for a question belonging to the attempt.
        Validates ownership, membership, and timer.
        """
        attempt = self._get_active_attempt(attempt_id, candidate_id)

        # Membership check
        assigned_ids = {item["question_id"] for item in attempt.assigned_questions}
        if question_id not in assigned_ids:
            raise QuestionNotInAttemptError(question_id)
        question = self.db.get(Question, question_id)
        valid_option_ids = {option.id for option in question.options} if question else set()
        if len(selected_option_ids) != len(set(selected_option_ids)) or not set(selected_option_ids).issubset(valid_option_ids):
            raise QuestionNotInAttemptError(question_id)

        # Upsert answer
        answer = (
            self.db.query(Answer)
            .filter(Answer.attempt_id == attempt_id, Answer.question_id == question_id)
            .with_for_update()
            .first()
        )
        if answer is None:
            answer = Answer(attempt_id=attempt_id, question_id=question_id)
            self.db.add(answer)

        answer.selected_ids = selected_option_ids
        answer.answered_at = datetime.utcnow()

        try:
            self.db.commit()
        except SQLIntegrityError:
            self.db.rollback()
            answer = (
                self.db.query(Answer)
                .filter(Answer.attempt_id == attempt_id, Answer.question_id == question_id)
                .with_for_update()
                .one()
            )
            answer.selected_ids = selected_option_ids
            answer.answered_at = datetime.utcnow()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(answer)
        return answer

    def clear_answer(
        self,
        attempt_id: int,
        question_id: int,
        *,
        candidate_id: Optional[int] = None,
    ) -> None:
        attempt = self._get_active_attempt(attempt_id, candidate_id)
        assigned_ids = {item["question_id"] for item in attempt.assigned_questions}
        if question_id not in assigned_ids:
            raise QuestionNotInAttemptError(question_id)

        answer = (
            self.db.query(Answer)
            .filter(Answer.attempt_id == attempt_id, Answer.question_id == question_id)
            .with_for_update()
            .first()
        )
        if answer:
            self.db.delete(answer)
            self.db.commit()

    # ------------------------------------------------------------------
    # Submit / Expire
    # ------------------------------------------------------------------

    def submit_attempt(
        self,
        attempt_id: int,
        *,
        candidate_id: Optional[int] = None,
        auto_expired: bool = False,
    ) -> Result:
        """
        Finalize the attempt, mark it, and create a Result.
        Idempotent: if already submitted, returns existing result.
        """
        attempt = (
            self.db.query(Attempt)
            .options(
                selectinload(Attempt.exam),
                selectinload(Attempt.answers),
            )
            .filter(Attempt.id == attempt_id)
            .first()
        )
        if not attempt:
            raise AttemptNotFoundError(attempt_id)

        if candidate_id is not None and attempt.candidate_id != candidate_id:
            raise AttemptNotFoundError(attempt_id)  # hide existence

        if attempt.status == AttemptStatus.SUBMITTED:
            if attempt.result:
                return attempt.result
            # Re-mark if result missing (edge case)
        elif attempt.status == AttemptStatus.EXPIRED and not auto_expired:
            raise ExamExpiredError()
        elif attempt.status not in (AttemptStatus.ACTIVE, AttemptStatus.EXPIRED):
            raise InvalidAttemptStateError(
                current=attempt.status.value,
                expected=AttemptStatus.ACTIVE.value,
            )

        if attempt.status in (AttemptStatus.ACTIVE, AttemptStatus.EXPIRED):
            result = (
                self.db.query(Result)
                .filter(Result.attempt_id == attempt.id)
                .with_for_update()
                .first()
            )
            if result:
                return result

        # Check expiry
        if attempt.is_expired() and attempt.status == AttemptStatus.ACTIVE:
            attempt.status = AttemptStatus.EXPIRED
            auto_expired = True

        now = datetime.utcnow()
        attempt.submitted_at = now
        attempt.status = AttemptStatus.SUBMITTED if not auto_expired else AttemptStatus.EXPIRED

        # Mark
        marker = MarkingEngine(self.db)
        marking = marker.mark_attempt(attempt)

        # Snapshot on attempt
        attempt.score = marking["score"]
        attempt.max_score = marking["max_score"]
        attempt.percentage = marking["percentage"]
        attempt.grade = marking["grade"]
        attempt.passed = marking["passed"]

        # Create or update Result
        result = attempt.result
        if result is None:
            result = Result(
                attempt_id=attempt.id,
                exam_id=attempt.exam_id,
                candidate_id=attempt.candidate_id,
            )
            self.db.add(result)

        result.score = marking["score"]
        result.max_score = marking["max_score"]
        result.percentage = marking["percentage"]
        result.grade = marking["grade"]
        result.passed = marking["passed"]
        result.correct_count = marking["correct_count"]
        result.incorrect_count = marking["incorrect_count"]
        result.unanswered_count = marking["unanswered_count"]
        result.time_used_seconds = marking["time_used_seconds"]
        result.breakdown = marking["breakdown"]
        result.submitted_at = now

        try:
            self.db.commit()
        except SQLIntegrityError:
            self.db.rollback()
            result = self.db.query(Result).filter(Result.attempt_id == attempt_id).first()
            if result:
                return result
            raise
        self.db.refresh(result)
        return result

    def check_and_expire(self, attempt_id: int) -> Optional[Result]:
        """If the attempt has expired, finalize it and return the result."""
        attempt = self.db.get(Attempt, attempt_id)
        if not attempt:
            return None
        if attempt.status == AttemptStatus.ACTIVE and attempt.is_expired():
            return self.submit_attempt(attempt_id, auto_expired=True)
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_active_attempt(
        self,
        attempt_id: int,
        candidate_id: Optional[int] = None,
    ) -> Attempt:
        attempt = (
            self.db.query(Attempt)
            .options(selectinload(Attempt.exam))
            .filter(Attempt.id == attempt_id)
            .first()
        )
        if not attempt:
            raise AttemptNotFoundError(attempt_id)
        if candidate_id is not None and attempt.candidate_id != candidate_id:
            raise AttemptNotFoundError(attempt_id)

        if attempt.status == AttemptStatus.SUBMITTED:
            raise AttemptAlreadySubmittedError()
        if attempt.status == AttemptStatus.EXPIRED or attempt.is_expired():
            # Auto-finalize
            self.submit_attempt(attempt_id, candidate_id=candidate_id, auto_expired=True)
            raise ExamExpiredError()
        if attempt.status != AttemptStatus.ACTIVE:
            raise AttemptNotActiveError()

        return attempt

    def _expire_attempt(self, attempt: Attempt) -> Result:
        return self.submit_attempt(attempt.id, auto_expired=True)

    def get_attempt_questions_for_candidate(
        self,
        attempt_id: int,
        candidate_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Return questions + options for the candidate WITHOUT correct-answer flags.
        """
        attempt = self._get_active_attempt(attempt_id, candidate_id)
        assigned = attempt.assigned_questions
        qids = [item["question_id"] for item in assigned]

        questions = {
            q.id: q
            for q in self.db.query(Question)
            .options(selectinload(Question.options))
            .filter(Question.id.in_(qids))
            .all()
        }

        # Index answers
        answer_map = {a.question_id: a for a in attempt.answers}

        result = []
        for item in assigned:
            q = questions.get(item["question_id"])
            if not q:
                continue
            option_order = item.get("option_order") or [o.id for o in q.options]
            opt_map = {o.id: o for o in q.options}
            options = []
            for oid in option_order:
                opt = opt_map.get(oid)
                if opt:
                    options.append({
                        "id": opt.id,
                        "text": opt.text,
                        "order": len(options),
                    })

            ans = answer_map.get(q.id)
            result.append({
                "question_id": q.id,
                "text": q.text,
                "marks": q.marks,
                "options": options,
                "selected_option_ids": ans.selected_ids if ans else [],
            })
        return result
