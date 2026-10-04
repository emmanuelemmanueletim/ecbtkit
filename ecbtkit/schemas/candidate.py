"""Candidate schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from ecbtkit.schemas.common import ORMModel


class CandidateCreate(BaseModel):
    full_name: str
    email: Optional[str] = None
    registration_number: Optional[str] = None
    external_id: Optional[str] = None
    user_id: Optional[int] = None


class CandidateOut(ORMModel):
    id: int
    full_name: str
    email: Optional[str] = None
    registration_number: Optional[str] = None
    external_id: Optional[str] = None
    status: str
    created_at: datetime
