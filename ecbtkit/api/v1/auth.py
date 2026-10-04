"""Authentication endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ecbtkit.auth.deps import get_current_user
from ecbtkit.auth.security import create_access_token, hash_password, verify_password
from ecbtkit.core.exceptions import InvalidCredentialsError, ValidationError
from ecbtkit.db.base import get_db
from ecbtkit.models.candidate import Candidate
from ecbtkit.models.user import User, UserRole
from ecbtkit.schemas.auth import Token, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise ValidationError("Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Auto-create candidate profile for candidate role
    if payload.role == UserRole.CANDIDATE:
        candidate = Candidate(
            user_id=user.id,
            full_name=payload.full_name or payload.email,
            email=payload.email,
        )
        db.add(candidate)

    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise InvalidCredentialsError()
    if not user.is_active:
        raise InvalidCredentialsError("Account is inactive")

    token = create_access_token(subject=str(user.id), role=user.role.value)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
