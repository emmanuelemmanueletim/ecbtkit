"""Unit tests for scoring and grading engines."""

import pytest

from ecbtkit.engine.scoring import GradingEngine, ScoringEngine, ScoringRule
from ecbtkit.core.exceptions import InvalidScoringRuleError


def test_basic_scoring():
    rule = ScoringRule(marks_correct=1.0, marks_wrong=0.0, marks_unanswered=0.0)
    engine = ScoringEngine(rule)
    result = engine.calculate_total([True, True, False, None, True])
    assert result["score"] == 3.0
    assert result["max_score"] == 5.0
    assert result["percentage"] == 60.0
    assert result["correct_count"] == 3
    assert result["incorrect_count"] == 1
    assert result["unanswered_count"] == 1


def test_negative_marking():
    rule = ScoringRule(marks_correct=1.0, marks_wrong=-0.25, marks_unanswered=0.0)
    engine = ScoringEngine(rule)
    result = engine.calculate_total([True, False, False, None])
    assert result["score"] == 0.5  # 1 - 0.25 - 0.25
    assert result["max_score"] == 4.0


def test_invalid_scoring_rule():
    with pytest.raises(InvalidScoringRuleError):
        ScoringRule(marks_correct=-1).validate()


def test_grading():
    scale = GradingEngine.default_scale()
    engine = GradingEngine(scale)
    assert engine.grade(85) == "A"
    assert engine.grade(65) == "B"
    assert engine.grade(35) == "F"
    assert engine.grade(40) == "E"
