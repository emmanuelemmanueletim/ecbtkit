"""
Deterministic randomization for questions and options within an attempt.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any, Dict, List, Sequence

from ecbtkit.models.question import Question


def make_seed(exam_id: int, candidate_id: int, attempt_id: int | None = None) -> str:
    """Create a deterministic seed string for an attempt."""
    raw = f"{exam_id}:{candidate_id}:{attempt_id or 0}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def shuffle_questions(
    questions: Sequence[Question],
    seed: str,
    enabled: bool = True,
) -> List[Question]:
    """Return questions in randomized (or original) order using the given seed."""
    items = list(questions)
    if not enabled or len(items) <= 1:
        return items
    rng = random.Random(seed + ":questions")
    rng.shuffle(items)
    return items


def shuffle_options(
    option_ids: Sequence[int],
    seed: str,
    question_id: int,
    enabled: bool = True,
) -> List[int]:
    """Return option IDs in randomized order for a specific question."""
    items = list(option_ids)
    if not enabled or len(items) <= 1:
        return items
    rng = random.Random(f"{seed}:options:{question_id}")
    rng.shuffle(items)
    return items


def build_assigned_payload(
    questions: Sequence[Question],
    seed: str,
    randomize_questions: bool = True,
    randomize_options: bool = True,
) -> List[Dict[str, Any]]:
    """
    Build the assigned_questions structure stored on an Attempt.

    Each entry:
    {
        "question_id": int,
        "option_order": [int, ...]   # ordered option IDs as presented to candidate
    }
    """
    ordered = shuffle_questions(questions, seed, enabled=randomize_questions)
    payload = []
    for q in ordered:
        opt_ids = [o.id for o in q.options]
        ordered_opts = shuffle_options(opt_ids, seed, q.id, enabled=randomize_options)
        payload.append({
            "question_id": q.id,
            "option_order": ordered_opts,
        })
    return payload
