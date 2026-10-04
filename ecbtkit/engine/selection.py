"""
Question Selection Engine.

Supports rules such as:
- Select N questions from a subject
- Select by topic quotas
- Select by difficulty quotas
- Combined rules
"""

from __future__ import annotations

import random
import re
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ecbtkit.core.exceptions import InsufficientQuestionsError
from ecbtkit.models.question import Difficulty, Question, QuestionStatus, Subject, Topic


class QuestionSelector:
    """
    Selects questions according to configurable rules.
    Always verifies that enough questions exist before returning.
    """

    def __init__(self, db: Session, seed: Optional[str] = None):
        self.db = db
        self.rng = random.Random(seed) if seed else random.Random()

    def select(
        self,
        total: int,
        subject: Optional[str] = None,
        subject_id: Optional[int] = None,
        topics: Optional[Dict[str, int]] = None,
        difficulty: Optional[Dict[str, int]] = None,
        tags: Optional[List[str]] = None,
        exclude_ids: Optional[Sequence[int]] = None,
    ) -> List[Question]:
        """
        Select questions according to the provided rules.

        Priority of rules:
        1. If topics dict is provided → allocate by topic quotas first.
        2. Else if difficulty dict is provided → allocate by difficulty.
        3. Else → simple random sample from the matching pool.

        Raises InsufficientQuestionsError if the pool cannot satisfy the request.
        """
        if type(total) is not int or total < 1:
            raise ValueError("total must be a positive integer")
        exclude_ids = set(exclude_ids or [])

        if (topics is not None and not isinstance(topics, dict)) or (difficulty is not None and not isinstance(difficulty, dict)):
            raise ValueError("topic and difficulty quotas must be objects")
        if topics and difficulty:
            raise ValueError("Combining topic and difficulty quotas is not supported; use one quota type")
        if topics:
            return self._select_by_topics(
                total=total,
                subject=subject,
                subject_id=subject_id,
                topics=topics,
                tags=tags,
                exclude_ids=exclude_ids,
            )

        if difficulty:
            return self._select_by_difficulty(
                total=total,
                subject=subject,
                subject_id=subject_id,
                difficulty=difficulty,
                tags=tags,
                exclude_ids=exclude_ids,
            )

        return self._select_simple(
            total=total,
            subject=subject,
            subject_id=subject_id,
            tags=tags,
            exclude_ids=exclude_ids,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _base_query(
        self,
        subject: Optional[str] = None,
        subject_id: Optional[int] = None,
        topic_id: Optional[int] = None,
        difficulty: Optional[Difficulty] = None,
        tags: Optional[List[str]] = None,
        exclude_ids: Optional[set] = None,
    ):
        q = (
            select(Question)
            .options(selectinload(Question.options))
            .where(Question.status == QuestionStatus.ACTIVE)
        )

        if subject_id is not None:
            q = q.where(Question.subject_id == subject_id)
        elif subject:
            sub = self.db.execute(
                select(Subject.id).where(Subject.name == subject)
            ).scalar_one_or_none()
            if sub is None:
                return q.where(False)  # empty
            q = q.where(Question.subject_id == sub)

        if topic_id is not None:
            q = q.where(Question.topic_id == topic_id)

        if difficulty is not None:
            q = q.where(Question.difficulty == difficulty)

        if tags and self.db.bind and self.db.bind.dialect.name in {"sqlite", "postgresql", "mysql", "mariadb"}:
            for tag in tags:
                escaped = re.escape(tag.strip())
                if not escaped:
                    continue
                q = q.where(Question.tags.regexp_match(rf"(^|,)\s*{escaped}\s*(,|$)", flags="i"))

        if exclude_ids:
            q = q.where(Question.id.notin_(exclude_ids))

        return q

    def _fetch_and_sample(self, query, count: int) -> List[Question]:
        questions = list(self.db.execute(query).scalars().all())
        if len(questions) < count:
            raise InsufficientQuestionsError(
                required=count,
                available=len(questions),
            )
        return self.rng.sample(questions, count)

    def _select_simple(
        self,
        total: int,
        subject: Optional[str],
        subject_id: Optional[int],
        tags: Optional[List[str]],
        exclude_ids: set,
    ) -> List[Question]:
        q = self._base_query(
            subject=subject,
            subject_id=subject_id,
            tags=tags,
            exclude_ids=exclude_ids,
        )
        return self._fetch_and_sample(q, total)

    def _select_by_topics(
        self,
        total: int,
        subject: Optional[str],
        subject_id: Optional[int],
        topics: Dict[str, int],
        tags: Optional[List[str]],
        exclude_ids: set,
    ) -> List[Question]:
        self._validate_quotas(total, topics)
        selected: List[Question] = []
        remaining_exclude = set(exclude_ids)

        for topic_name, quota in topics.items():
            if quota <= 0:
                continue
            topic = self.db.execute(
                select(Topic).where(Topic.name == topic_name)
            ).scalar_one_or_none()
            if topic is None:
                raise InsufficientQuestionsError(
                    required=quota,
                    available=0,
                    criteria={"topic": topic_name},
                )
            q = self._base_query(
                subject=subject,
                subject_id=subject_id or topic.subject_id,
                topic_id=topic.id,
                tags=tags,
                exclude_ids=remaining_exclude,
            )
            batch = self._fetch_and_sample(q, quota)
            selected.extend(batch)
            remaining_exclude.update(q.id for q in batch)

        # Fill remaining slots from the broader pool if total > sum(quotas)
        allocated = sum(topics.values())
        if total > allocated:
            extra = total - allocated
            q = self._base_query(
                subject=subject,
                subject_id=subject_id,
                tags=tags,
                exclude_ids=remaining_exclude,
            )
            extras = self.db.execute(q).scalars().all()
            if len(extras) < extra:
                raise InsufficientQuestionsError(total, len(selected) + len(extras), {"topics": topics})
            selected.extend(self.rng.sample(extras, extra))

        if len(selected) < total:
            raise InsufficientQuestionsError(total, len(selected), {"topics": topics})

        return selected

    def _select_by_difficulty(
        self,
        total: int,
        subject: Optional[str],
        subject_id: Optional[int],
        difficulty: Dict[str, int],
        tags: Optional[List[str]],
        exclude_ids: set,
    ) -> List[Question]:
        self._validate_quotas(total, difficulty)
        selected: List[Question] = []
        remaining_exclude = set(exclude_ids)

        for diff_name, quota in difficulty.items():
            if quota <= 0:
                continue
            try:
                diff_enum = Difficulty(diff_name.lower())
            except ValueError:
                raise InsufficientQuestionsError(
                    required=quota,
                    available=0,
                    criteria={"difficulty": diff_name},
                )
            q = self._base_query(
                subject=subject,
                subject_id=subject_id,
                difficulty=diff_enum,
                tags=tags,
                exclude_ids=remaining_exclude,
            )
            batch = self._fetch_and_sample(q, quota)
            selected.extend(batch)
            remaining_exclude.update(q.id for q in batch)

        allocated = sum(difficulty.values())
        if total > allocated:
            extra = total - allocated
            q = self._base_query(
                subject=subject,
                subject_id=subject_id,
                tags=tags,
                exclude_ids=remaining_exclude,
            )
            extras = self.db.execute(q).scalars().all()
            if len(extras) < extra:
                raise InsufficientQuestionsError(total, len(selected) + len(extras), {"difficulty": difficulty})
            selected.extend(self.rng.sample(extras, extra))

        if len(selected) < total:
            raise InsufficientQuestionsError(total, len(selected), {"difficulty": difficulty})

        return selected

    @staticmethod
    def _validate_quotas(total: int, quotas: Dict[str, int]) -> None:
        if total < 1 or any(type(value) is not int or value < 0 for value in quotas.values()):
            raise ValueError("total and question quotas must be positive integers")
        allocated = sum(quotas.values())
        if allocated > total:
            raise ValueError("question quotas cannot exceed total")
