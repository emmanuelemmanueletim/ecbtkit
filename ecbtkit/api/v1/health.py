"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ecbtkit.db.base import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "ecbtkit"}


@router.get("/health/database")
def health_database(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "error", "database": str(exc)}
