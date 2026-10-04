"""
Password hashing and policy enforcement.

Uses Argon2id (winner of Password Hashing Competition) when argon2-cffi
is installed; falls back to PBKDF2-HMAC-SHA256.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from typing import List, Tuple

from ecbtkit.core.config import get_settings
from ecbtkit.core.exceptions import PasswordPolicyError

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, InvalidHashError

    _ph = PasswordHasher(
        time_cost=3,
        memory_cost=65536,  # 64 MB
        parallelism=2,
        hash_len=32,
        salt_len=16,
    )
    _HAS_ARGON2 = True
except ImportError:
    _HAS_ARGON2 = False
    _ph = None


def hash_password(password: str) -> str:
    """Hash a password for storage. Never store plain text."""
    if _HAS_ARGON2:
        return _ph.hash(password)
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode(), 200_000)
    return f"pbkdf2_sha256$200000${salt}${digest.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time verification where possible."""
    if not hashed:
        return False
    if _HAS_ARGON2 and hashed.startswith("$argon2"):
        try:
            return _ph.verify(hashed, plain)
        except (VerifyMismatchError, InvalidHashError, Exception):
            return False
    if hashed.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, digest_hex = hashed.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256", plain.encode("utf-8"), salt.encode(), int(iterations)
            )
            return hmac.compare_digest(digest.hex(), digest_hex)
        except Exception:
            return False
    # Legacy fallback from v0.1
    if hashed.startswith("pbkdf2:"):
        try:
            _, salt, digest_hex = hashed.split(":")
            digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 100_000)
            return hmac.compare_digest(digest.hex(), digest_hex)
        except Exception:
            return False
    return False


def needs_rehash(hashed: str) -> bool:
    """True if the stored hash should be upgraded (e.g. after policy change)."""
    if _HAS_ARGON2 and hashed.startswith("$argon2"):
        try:
            return _ph.check_needs_rehash(hashed)
        except Exception:
            return True
    return not hashed.startswith("$argon2")


def validate_password_strength(password: str) -> None:
    """
    Enforce configurable password policy.
    Raises PasswordPolicyError with a list of violations.
    """
    settings = get_settings()
    violations: List[str] = []

    if len(password) < settings.password_min_length:
        violations.append(f"Password must be at least {settings.password_min_length} characters")
    if len(password) > settings.password_max_length:
        violations.append(f"Password must be at most {settings.password_max_length} characters")
    if settings.password_require_uppercase and not re.search(r"[A-Z]", password):
        violations.append("Password must contain at least one uppercase letter")
    if settings.password_require_lowercase and not re.search(r"[a-z]", password):
        violations.append("Password must contain at least one lowercase letter")
    if settings.password_require_digit and not re.search(r"\d", password):
        violations.append("Password must contain at least one digit")
    if settings.password_require_special and not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'/`~]", password):
        violations.append("Password must contain at least one special character")

    # Common weak passwords (short list — extend in production)
    weak = {"password", "password1", "12345678", "qwerty123", "admin123", "letmein1"}
    if password.lower() in weak:
        violations.append("Password is too common")

    if violations:
        raise PasswordPolicyError(
            "Password does not meet security requirements",
            details={"violations": violations},
        )


def generate_secure_token(nbytes: int = 32) -> str:
    """URL-safe random token for verification / password-reset links."""
    return secrets.token_urlsafe(nbytes)
