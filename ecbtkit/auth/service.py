"""
Authentication service — signup, login, refresh, lockout, password reset.

This module is framework-independent (no HTTP). HTTP routes call into it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from ecbtkit.core.config import get_settings
from ecbtkit.core.exceptions import (
    AccountDisabledError,
    AccountLockedError,
    ConflictError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    NotFoundError,
    TokenInvalidError,
    ValidationError,
)
from ecbtkit.models.candidate import Candidate
from ecbtkit.models.user import User, UserRole
from ecbtkit.security.passwords import (
    generate_secure_token,
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from ecbtkit.security.tokens import create_token_pair, decode_token


class AuthService:
    """Production auth operations against the SQL user store."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Signup
    # ------------------------------------------------------------------

    def signup(
        self,
        *,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role: UserRole = UserRole.CANDIDATE,
        auto_verify: Optional[bool] = None,
    ) -> Tuple[User, Dict[str, str]]:
        email = email.strip().lower()
        if not email or "@" not in email:
            raise ValidationError("A valid email address is required")

        validate_password_strength(password)

        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            raise ConflictError("An account with this email already exists")

        # Only administrators may create other administrators via API
        if role == UserRole.ADMINISTRATOR:
            # Allow first user to be admin when no users exist
            if self.db.query(User).count() > 0:
                raise ValidationError("Cannot self-register as administrator")

        verify = auto_verify if auto_verify is not None else (
            not self.settings.require_email_verification
        )

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=True,
            is_verified=verify,
        )
        self.db.add(user)
        self.db.flush()

        if role == UserRole.CANDIDATE:
            self.db.add(
                Candidate(
                    user_id=user.id,
                    full_name=full_name or email.split("@")[0],
                    email=email,
                )
            )

        self.db.commit()
        self.db.refresh(user)

        tokens = create_token_pair(str(user.id), user.role.value)
        return user, tokens

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self, *, email: str, password: str, ip: Optional[str] = None) -> Dict[str, Any]:
        email = email.strip().lower()
        user = self.db.query(User).filter(User.email == email).first()

        # Uniform response timing: always verify something
        if not user:
            # Dummy hash work to reduce timing oracle
            verify_password(password, hash_password("dummy-timing-guard"))
            raise InvalidCredentialsError()

        self._check_lockout(user)

        if not verify_password(password, user.hashed_password):
            self._register_failed_login(user)
            raise InvalidCredentialsError()

        if not user.is_active:
            raise AccountDisabledError()

        if self.settings.require_email_verification and not user.is_verified:
            raise EmailNotVerifiedError()

        # Upgrade hash if algorithm parameters changed
        if needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(password)

        self._clear_failed_logins(user)
        user.last_login_at = datetime.utcnow()
        self.db.commit()

        tokens = create_token_pair(str(user.id), user.role.value)
        return {
            **tokens,
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "is_verified": user.is_verified,
            },
        }

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self, refresh_token: str) -> Dict[str, str]:
        payload = decode_token(refresh_token, expected_type="refresh")
        user_id = payload.get("sub")
        if not user_id:
            raise TokenInvalidError()
        user = self.db.get(User, int(user_id))
        if not user or not user.is_active:
            raise TokenInvalidError("User no longer valid")
        return create_token_pair(str(user.id), user.role.value)

    # ------------------------------------------------------------------
    # Password change / reset
    # ------------------------------------------------------------------

    def change_password(self, user: User, current: str, new_password: str) -> None:
        if not verify_password(current, user.hashed_password):
            raise InvalidCredentialsError("Current password is incorrect")
        validate_password_strength(new_password)
        user.hashed_password = hash_password(new_password)
        self.db.commit()

    def request_password_reset(self, email: str) -> str:
        """
        Generate a one-time reset token.
        Always returns a token-shaped string so callers cannot enumerate emails.
        In production, email the token only if the user exists.
        """
        email = email.strip().lower()
        token = generate_secure_token(32)
        user = self.db.query(User).filter(User.email == email).first()
        if user:
            user.reset_token = token
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            self.db.commit()
        return token

    def reset_password(self, token: str, new_password: str) -> None:
        validate_password_strength(new_password)
        user = (
            self.db.query(User)
            .filter(User.reset_token == token)
            .first()
        )
        if not user or not user.reset_token_expires:
            raise TokenInvalidError("Invalid or expired reset token")
        if user.reset_token_expires < datetime.utcnow():
            raise TokenInvalidError("Reset token has expired")
        user.hashed_password = hash_password(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        self._clear_failed_logins(user)
        self.db.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_lockout(self, user: User) -> None:
        if user.locked_until and user.locked_until > datetime.utcnow():
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
            raise AccountLockedError(minutes=remaining)

    def _register_failed_login(self, user: User) -> None:
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= self.settings.max_login_attempts:
            user.locked_until = datetime.utcnow() + timedelta(
                minutes=self.settings.lockout_duration_minutes
            )
            user.failed_login_attempts = 0
        self.db.commit()

    def _clear_failed_logins(self, user: User) -> None:
        user.failed_login_attempts = 0
        user.locked_until = None
