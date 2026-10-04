"""Request helpers: auth extraction, DB session, client IP."""

from __future__ import annotations

import secrets
from typing import Optional

from starlette.requests import Request
from sqlalchemy.orm import Session

from ecbtkit.core.exceptions import AuthenticationError, AuthorizationError
from ecbtkit.db.base import get_session_factory
from ecbtkit.models.user import User, UserRole
from ecbtkit.security.tokens import decode_token


def get_client_ip(request: Request) -> str:
    # Forwarded headers are attacker-controlled unless a trusted proxy has
    # already normalized them. Use the transport peer address by default.
    if request.client:
        return request.client.host
    return "unknown"


def open_db() -> Session:
    return get_session_factory()()


def get_bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth:
        return None
    parts = auth.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def get_current_user(request: Request, db: Session) -> User:
    token = get_bearer_token(request)
    if not token:
        raise AuthenticationError("Bearer token required")
    payload = decode_token(token, expected_type="access")
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token payload")
    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    token_jti = payload.get("jti")
    if token_jti and (not user.refresh_token_jti or not secrets.compare_digest(token_jti, user.refresh_token_jti)):
        raise AuthenticationError("Token has been revoked")
    if "ver" in payload and int(payload["ver"]) != user.token_version:
        raise AuthenticationError("Token has been revoked")
    return user


def require_roles(user: User, *roles: UserRole) -> None:
    if user.role == UserRole.ADMINISTRATOR:
        return
    if user.role not in roles:
        raise AuthorizationError(
            f"Requires one of: {[r.value for r in roles]}"
        )
