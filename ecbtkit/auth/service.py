"""
Authentication service — framework-independent.

Public signup is candidate-only. Staff accounts are provisioned via CLI.
Verification and reset tokens are stored as hashes only and never returned over HTTP.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.exc import IntegrityError as SQLIntegrityError
from sqlalchemy.orm import Session

from ecbtkit.core.config import get_settings
from ecbtkit.core.exceptions import (
    AccountDisabledError,
    AccountLockedError,
    ConflictError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    TokenInvalidError,
    ValidationError,
)
from ecbtkit.mail.service import EmailService
from ecbtkit.models.attempt import Attempt, AttemptStatus
from ecbtkit.models.candidate import Candidate
from ecbtkit.models.user import User, UserRole
from ecbtkit.security.passwords import (
    generate_secure_token,
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from ecbtkit.security.tokens import create_token_pair_for_user, decode_token


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(expires: Optional[datetime]) -> bool:
    if expires is None:
        return True
    now = _utcnow()
    # SQLite often returns naive datetimes
    if expires.tzinfo is None:
        return expires < now.replace(tzinfo=None)
    return expires < now



class AuthService:
    def __init__(self, db: Session, mail: Optional[EmailService] = None):
        self.db = db
        self.settings = get_settings()
        self.mail = mail or EmailService(self.settings)

    # ------------------------------------------------------------------
    # Signup / verification
    # ------------------------------------------------------------------

    def signup(
        self,
        *,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role: UserRole = UserRole.CANDIDATE,
        auto_verify: Optional[bool] = None,
    ) -> Tuple[User, Optional[Dict[str, str]]]:
        """
        Register a candidate.

        Returns (user, tokens). tokens is None when email verification is required
        — the client must verify before obtaining usable credentials.
        """
        email = email.strip().lower()
        if not email or "@" not in email:
            raise ValidationError("A valid email address is required")
        validate_password_strength(password)

        if role != UserRole.CANDIDATE:
            raise ValidationError("Only candidates may self-register")

        verified = auto_verify if auto_verify is not None else (
            not self.settings.require_email_verification
        )

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=True,
            is_verified=verified,
            refresh_token_jti=secrets.token_urlsafe(24) if verified else None,
        )
        self.db.add(user)
        try:
            self.db.flush()
            self.db.add(
                Candidate(
                    user_id=user.id,
                    full_name=full_name or email.split("@")[0],
                    email=email,
                )
            )
            verification_raw: Optional[str] = None
            if not verified:
                verification_raw = generate_secure_token(32)
                user.verification_token_hash = _hash_token(verification_raw)
                user.verification_token_expires = _utcnow() + timedelta(hours=24)

            self.db.commit()
            self.db.refresh(user)
        except SQLIntegrityError as exc:
            self.db.rollback()
            raise ConflictError("An account with this email already exists") from exc

        if verification_raw:
            result = self.mail.send_verification(
                to=user.email, token=verification_raw, full_name=user.full_name
            )
            if not result.ok and not self.settings.mail_async:
                # Token is already durable in DB; delivery failed — surface generically later
                pass

        if not verified:
            return user, None
        return user, create_token_pair_for_user(user)

    def verify_email(self, token: str) -> User:
        """Validate a single-use verification token and mark the account verified."""
        if not token or len(token) < 16:
            raise TokenInvalidError("Invalid or expired verification token")
        token_hash = _hash_token(token)
        user = (
            self.db.query(User)
            .filter(User.verification_token_hash == token_hash)
            .first()
        )
        if not user or not user.verification_token_expires:
            raise TokenInvalidError("Invalid or expired verification token")
        if _is_expired(user.verification_token_expires):
            raise TokenInvalidError("Verification token has expired")

        user.is_verified = True
        user.verification_token_hash = None
        user.verification_token_expires = None
        user.refresh_token_jti = secrets.token_urlsafe(24)
        self.db.commit()
        self.db.refresh(user)
        return user

    # ------------------------------------------------------------------
    # Login / refresh / logout
    # ------------------------------------------------------------------

    def login(self, *, email: str, password: str, ip: Optional[str] = None) -> Dict[str, Any]:
        email = email.strip().lower()
        user = self.db.query(User).filter(User.email == email).first()

        if not user:
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

        if needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(password)

        self._clear_failed_logins(user)
        user.last_login_at = _utcnow()
        user.refresh_token_jti = secrets.token_urlsafe(24)
        self.db.commit()

        tokens = create_token_pair_for_user(user)
        if ip:
            try:
                self.mail.send_new_signin(to=user.email, ip=ip, full_name=user.full_name)
            except Exception:
                pass
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

    def refresh(self, refresh_token: str) -> Dict[str, str]:
        payload = decode_token(refresh_token, expected_type="refresh")
        user_id = payload.get("sub")
        if not user_id:
            raise TokenInvalidError()
        user = self.db.get(User, int(user_id))
        if not user or not user.is_active:
            raise TokenInvalidError("User no longer valid")
        if self.settings.require_email_verification and not user.is_verified:
            raise EmailNotVerifiedError()
        if "ver" in payload and int(payload["ver"]) != user.token_version:
            raise TokenInvalidError("Refresh token has been revoked")
        jti = payload.get("jti")
        if not jti or not user.refresh_token_jti or not secrets.compare_digest(jti, user.refresh_token_jti):
            raise TokenInvalidError("Refresh token has been rotated or revoked")
        # Single-use: rotate jti
        user.refresh_token_jti = secrets.token_urlsafe(24)
        self.db.commit()
        return create_token_pair_for_user(user)

    def logout(self, user: User) -> None:
        user.refresh_token_jti = None
        user.token_version += 1
        self.db.commit()

    # ------------------------------------------------------------------
    # Password change / reset
    # ------------------------------------------------------------------

    def change_password(self, user: User, current: str, new_password: str) -> None:
        if not verify_password(current, user.hashed_password):
            raise InvalidCredentialsError("Current password is incorrect")
        validate_password_strength(new_password)
        user.hashed_password = hash_password(new_password)
        user.refresh_token_jti = None
        user.token_version += 1
        if user.candidate_profile:
            self.db.query(Attempt).filter(
                Attempt.candidate_id == user.candidate_profile.id,
                Attempt.status == AttemptStatus.ACTIVE,
            ).update({Attempt.status: AttemptStatus.CANCELLED}, synchronize_session=False)
        self.db.commit()
        try:
            self.mail.send_password_changed(to=user.email, full_name=user.full_name)
        except Exception:
            pass

    def request_password_reset(self, email: str) -> None:
        """Always same external behaviour — no account enumeration. Token never returned."""
        email = email.strip().lower()
        token = generate_secure_token(32)
        user = self.db.query(User).filter(User.email == email).first()
        if user:
            user.reset_token_hash = _hash_token(token)
            user.reset_token_expires = _utcnow() + timedelta(hours=1)
            self.db.commit()
            self.mail.send_password_reset(
                to=user.email, token=token, full_name=user.full_name
            )

    def reset_password(self, token: str, new_password: str) -> None:
        validate_password_strength(new_password)
        if not token or len(token) < 16:
            raise TokenInvalidError("Invalid or expired reset token")
        token_hash = _hash_token(token)
        user = self.db.query(User).filter(User.reset_token_hash == token_hash).first()
        if not user or not user.reset_token_expires:
            raise TokenInvalidError("Invalid or expired reset token")
        if _is_expired(user.reset_token_expires):
            raise TokenInvalidError("Reset token has expired")

        user.hashed_password = hash_password(new_password)
        user.refresh_token_jti = None
        user.token_version += 1
        user.reset_token_hash = None
        user.reset_token_expires = None
        if user.candidate_profile:
            self.db.query(Attempt).filter(
                Attempt.candidate_id == user.candidate_profile.id,
                Attempt.status == AttemptStatus.ACTIVE,
            ).update({Attempt.status: AttemptStatus.CANCELLED}, synchronize_session=False)
        self.db.commit()
        try:
            self.mail.send_password_changed(to=user.email, full_name=user.full_name)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_lockout(self, user: User) -> None:
        if user.locked_until and not _is_expired(user.locked_until):
            remaining = int((user.locked_until - _utcnow()).total_seconds() / 60) + 1
            raise AccountLockedError(minutes=remaining)

    def _register_failed_login(self, user: User) -> None:
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= self.settings.max_login_attempts:
            user.locked_until = _utcnow() + timedelta(
                minutes=self.settings.lockout_duration_minutes
            )
            user.failed_login_attempts = 0
        self.db.commit()

    def _clear_failed_logins(self, user: User) -> None:
        user.failed_login_attempts = 0
        user.locked_until = None
