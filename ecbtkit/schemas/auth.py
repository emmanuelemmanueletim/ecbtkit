"""Authentication schemas."""

from typing import Optional

from pydantic import BaseModel, Field

from ecbtkit.models.user import UserRole
from ecbtkit.schemas.common import ORMModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    role: str
    exp: Optional[int] = None


class UserCreate(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(min_length=6)
    full_name: Optional[str] = None
    role: UserRole = UserRole.CANDIDATE


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(ORMModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
