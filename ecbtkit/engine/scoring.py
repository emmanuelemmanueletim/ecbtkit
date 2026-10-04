"""
Scoring and Grading engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from ecbtkit.core.exceptions import InvalidGradingScaleError, InvalidScoringRuleError


@dataclass
class ScoringRule:
    marks_correct: float = 1.0
    marks_wrong: float = 0.0
    marks_unanswered: float = 0.0

    def validate(self) -> None:
        if self.marks_correct < 0:
            raise InvalidScoringRuleError("marks_correct must be >= 0")


@dataclass
class GradeBand:
    min_percentage: float
    max_percentage: float
    grade: str

    def contains(self, percentage: float) -> bool:
        return self.min_percentage <= percentage <= self.max_percentage


class ScoringEngine:
    """Applies scoring rules to a set of answer evaluations."""

    def __init__(self, rule: ScoringRule):
        rule.validate()
        self.rule = rule

    def score_answer(self, is_correct: Optional[bool]) -> float:
        """
        is_correct:
          True  → correct
          False → wrong
          None  → unanswered
        """
        if is_correct is True:
            return self.rule.marks_correct
        if is_correct is False:
            return self.rule.marks_wrong
        return self.rule.marks_unanswered

    def calculate_total(
        self,
        evaluations: Sequence[Optional[bool]],
    ) -> Dict[str, Any]:
        """
        evaluations: list of True/False/None for each question.
        Returns score, max_score, percentage, counts.
        """
        score = 0.0
        correct = incorrect = unanswered = 0
        for ev in evaluations:
            score += self.score_answer(ev)
            if ev is True:
                correct += 1
            elif ev is False:
                incorrect += 1
            else:
                unanswered += 1

        max_score = len(evaluations) * self.rule.marks_correct
        percentage = (score / max_score * 100.0) if max_score > 0 else 0.0

        return {
            "score": round(score, 4),
            "max_score": round(max_score, 4),
            "percentage": round(percentage, 2),
            "correct_count": correct,
            "incorrect_count": incorrect,
            "unanswered_count": unanswered,
        }


class GradingEngine:
    """Maps a percentage to a grade using a configurable scale."""

    def __init__(self, bands: Optional[List[Dict[str, Any]]] = None):
        self.bands: List[GradeBand] = []
        if bands:
            self._load(bands)

    def _load(self, bands: List[Dict[str, Any]]) -> None:
        parsed = []
        for b in bands:
            try:
                parsed.append(
                    GradeBand(
                        min_percentage=float(b["min"]),
                        max_percentage=float(b["max"]),
                        grade=str(b["grade"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise InvalidGradingScaleError(f"Invalid band: {b}") from exc
        # Sort descending by min so first match wins for overlapping ranges
        parsed.sort(key=lambda x: x.min_percentage, reverse=True)
        self.bands = parsed

    def grade(self, percentage: float) -> Optional[str]:
        for band in self.bands:
            if band.contains(percentage):
                return band.grade
        return None

    @staticmethod
    def default_scale() -> List[Dict[str, Any]]:
        """A common Nigerian-style scale; developers should override."""
        return [
            {"min": 70, "max": 100, "grade": "A"},
            {"min": 60, "max": 69.99, "grade": "B"},
            {"min": 50, "max": 59.99, "grade": "C"},
            {"min": 45, "max": 49.99, "grade": "D"},
            {"min": 40, "max": 44.99, "grade": "E"},
            {"min": 0, "max": 39.99, "grade": "F"},
        ]
