"""
JWT-style access + refresh tokens using HMAC-SHA256 (stdlib only).

No external jose dependency required — keeps the framework independent.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from ecbtkit.core.config import get_settings
from ecbtkit.core.exceptions import TokenExpiredError, TokenInvalidError


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _sign(message: str, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(sig)


def create_token(
    claims: Dict[str, Any],
    *,
    expires_delta: Optional[timedelta] = None,
    token_type: str = "access",
) -> str:
    settings = get_settings()
    now = int(time.time())
    if expires_delta is None:
        if token_type == "refresh":
            expires_delta = timedelta(days=settings.refresh_token_expire_days)
        else:
            expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        **claims,
        "iat": now,
        "exp": now + int(expires_delta.total_seconds()),
        "type": token_type,
    }
    if token_type == "refresh" and "jti" not in payload:
        payload["jti"] = secrets.token_urlsafe(24)
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _sign(f"{header}.{body}", settings.secret_key)
    return f"{header}.{body}.{signature}"


def decode_token(token: str, *, expected_type: Optional[str] = None) -> Dict[str, Any]:
    settings = get_settings()
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise TokenInvalidError("Malformed token")
        header_b64, body_b64, sig_b64 = parts
        expected_sig = _sign(f"{header_b64}.{body_b64}", settings.secret_key)
        if not hmac.compare_digest(expected_sig, sig_b64):
            raise TokenInvalidError("Invalid token signature")
        payload = json.loads(_b64url_decode(body_b64))
        exp = payload.get("exp")
        if exp is None:
            raise TokenInvalidError("Token expiry is required")
        if int(exp) <= int(time.time()):
            raise TokenExpiredError()
        if expected_type and payload.get("type") != expected_type:
            raise TokenInvalidError(f"Expected {expected_type} token")
        return payload
    except (TokenExpiredError, TokenInvalidError):
        raise
    except Exception as exc:
        raise TokenInvalidError("Invalid or corrupted token") from exc


def create_access_token(subject: str, role: str, extra: Optional[Dict[str, Any]] = None) -> str:
    claims: Dict[str, Any] = {"sub": str(subject), "role": role}
    if extra:
        claims.update(extra)
    return create_token(claims, token_type="access")


def create_token_pair_for_user(user) -> Dict[str, str]:
    """Issue a pair bound to the user's token version and refresh JTI."""
    if not user.refresh_token_jti:
        user.refresh_token_jti = secrets.token_urlsafe(24)
    claims = {"sub": str(user.id), "role": user.role.value, "ver": user.token_version}
    access_token = create_access_token(str(user.id), user.role.value, extra={"ver": user.token_version})
    refresh_token = create_token(
        {**claims, "jti": user.refresh_token_jti}, token_type="refresh"
    )
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


def create_refresh_token(subject: str, role: str, jti: Optional[str] = None) -> str:
    claims: Dict[str, Any] = {"sub": str(subject), "role": role}
    if jti:
        claims["jti"] = jti
    return create_token(claims, token_type="refresh")


def create_token_pair(subject: str, role: str, jti: Optional[str] = None) -> Dict[str, str]:
    access_extra = {"jti": jti} if jti else None
    return {
        "access_token": create_access_token(subject, role, extra=access_extra),
        "refresh_token": create_refresh_token(subject, role, jti=jti),
        "token_type": "bearer",
    }
