"""
Marking Engine — automatically evaluates objective questions.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session, selectinload

from ecbtkit.models.attempt import Answer, Attempt
from ecbtkit.models.question import Question, QuestionType
from ecbtkit.engine.scoring import GradingEngine


class MarkingEngine:
    """
    Retrieves submitted answers, compares against correct options,
    applies scoring rules, and produces a result summary.
    """

    def __init__(self, db: Session):
        self.db = db

    def mark_attempt(self, attempt: Attempt) -> Dict:
        """
        Mark all answers belonging to the attempt.
        Returns a dict suitable for creating a Result record.
        """
        exam = attempt.exam

        # Load assigned question IDs
        assigned = attempt.assigned_questions
        question_ids = [item["question_id"] for item in assigned]

        # Load questions with options
        questions = {
            q.id: q
            for q in self.db.query(Question)
            .options(selectinload(Question.options))
            .filter(Question.id.in_(question_ids))
            .all()
        }

        # Index answers by question_id
        answer_map: Dict[int, Answer] = {
            a.question_id: a for a in attempt.answers
        }

        evaluations: List[Optional[bool]] = []
        breakdown = []
        score = max_score = 0.0

        for item in assigned:
            qid = item["question_id"]
            question = questions.get(qid)
            if not question:
                evaluations.append(None)
                continue

            answer = answer_map.get(qid)
            selected = answer.selected_ids if answer else []

            is_correct = self._evaluate(question, selected)
            correct_marks = question.marks
            wrong_marks = exam.marks_wrong
            unanswered_marks = exam.marks_unanswered
            answer_marks = (
                correct_marks if is_correct is True
                else wrong_marks if is_correct is False
                else unanswered_marks
            )
            score += answer_marks
            max_score += correct_marks

            # Persist marking info on the answer row
            if answer:
                answer.is_correct = is_correct
                answer.marks_awarded = answer_marks
            elif selected:  # shouldn't normally happen
                pass

            evaluations.append(is_correct)
            breakdown.append({
                "question_id": qid,
                "selected": selected,
                "is_correct": is_correct,
                "marks": answer_marks,
            })

        counts = {True: 0, False: 0, None: 0}
        for evaluation in evaluations:
            counts[evaluation] += 1
        totals = {
            "score": round(score, 4),
            "max_score": round(max_score, 4),
            "percentage": round(score / max_score * 100.0, 2) if max_score else 0.0,
            "correct_count": counts[True],
            "incorrect_count": counts[False],
            "unanswered_count": counts[None],
        }

        # Grading
        grader = GradingEngine(exam.grading_scale or None)
        if not exam.grading_scale:
            grader = GradingEngine(GradingEngine.default_scale())
        grade = grader.grade(totals["percentage"])

        passed = totals["percentage"] >= exam.pass_mark

        # Time used
        time_used = None
        if attempt.started_at and attempt.submitted_at:
            start = attempt.started_at.replace(tzinfo=None) if attempt.started_at.tzinfo else attempt.started_at
            end = attempt.submitted_at.replace(tzinfo=None) if attempt.submitted_at.tzinfo else attempt.submitted_at
            time_used = int((end - start).total_seconds())

        return {
            "score": totals["score"],
            "max_score": totals["max_score"],
            "percentage": totals["percentage"],
            "grade": grade,
            "passed": passed,
            "correct_count": totals["correct_count"],
            "incorrect_count": totals["incorrect_count"],
            "unanswered_count": totals["unanswered_count"],
            "time_used_seconds": time_used,
            "breakdown": breakdown,
        }

    def _evaluate(self, question: Question, selected_ids: List[int]) -> Optional[bool]:
        """
        Compare selected option IDs against the correct ones.
        Returns True / False / None (unanswered).
        """
        if not selected_ids:
            return None

        correct_ids: Set[int] = {o.id for o in question.options if o.is_correct}

        if question.question_type in (
            QuestionType.SINGLE_CHOICE,
            QuestionType.TRUE_FALSE,
        ):
            # Exactly one selection expected
            if len(selected_ids) != 1:
                return False
            return selected_ids[0] in correct_ids

        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            # All correct and no incorrect must be selected
            selected_set = set(selected_ids)
            return selected_set == correct_ids

        # Fallback
        return set(selected_ids) == correct_ids
