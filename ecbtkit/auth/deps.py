"""
FastAPI dependencies for authentication and authorization.
"""

from typing import Optional

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ecbtkit.auth.security import decode_access_token
from ecbtkit.core.exceptions import AuthenticationError, AuthorizationError
from ecbtkit.db.base import get_db
from ecbtkit.models.user import User, UserRole

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthenticationError("Bearer token required")
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token payload")
    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if credentials is None:
        return None
    try:
        return get_current_user(credentials, db)
    except AuthenticationError:
        return None


def require_roles(*roles: UserRole):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles and user.role != UserRole.ADMINISTRATOR:
            raise AuthorizationError(
                f"Requires one of roles: {[r.value for r in roles]}"
            )
        return user
    return dependency


# Convenience
require_admin = require_roles(UserRole.ADMINISTRATOR)
require_examiner = require_roles(UserRole.EXAMINER, UserRole.ADMINISTRATOR)
require_candidate = require_roles(UserRole.CANDIDATE, UserRole.ADMINISTRATOR)
