"""Shared API dependencies."""

from sqlalchemy.orm import Session

from ecbtkit.db.base import get_db  # re-export
from ecbtkit.engine.attempt_service import AttemptService


def get_attempt_service(db: Session = None) -> AttemptService:
    # Used when injecting manually; prefer Depends(get_db) in routes
    return AttemptService(db)
