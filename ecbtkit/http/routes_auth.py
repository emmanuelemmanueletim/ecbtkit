"""Auth HTTP routes — signup, login, refresh, password reset, me."""

from __future__ import annotations

import json
from typing import Any, Dict

from starlette.requests import Request
from starlette.routing import Route

from ecbtkit.auth.service import AuthService
from ecbtkit.core.config import get_settings
from ecbtkit.core.exceptions import ECBTError, ValidationError
from ecbtkit.http.deps import get_client_ip, get_current_user, open_db
from ecbtkit.http.responses import APIResponse, error_response, internal_error_response
from ecbtkit.models.user import UserRole
from ecbtkit.security.rate_limit import client_key, limiter


async def _read_json(request: Request) -> Dict[str, Any]:
    try:
        return await request.json()
    except Exception:
        raise ValidationError("Request body must be valid JSON")


async def signup(request: Request):
    settings = get_settings()
    ip = get_client_ip(request)
    try:
        limiter.check(client_key(ip, "signup"), limit=settings.auth_rate_limit_requests,
                      window=settings.auth_rate_limit_window_seconds)
        body = await _read_json(request)
        email = body.get("email")
        password = body.get("password")
        if not email or not password or len(password) > get_settings().password_max_length:
            raise ValidationError("email and password are required")
        role_str = body.get("role", "candidate")
        try:
            role = UserRole(role_str)
        except ValueError:
            raise ValidationError(f"Invalid role: {role_str}")
        if role != UserRole.CANDIDATE:
            raise ValidationError("Only candidates may self-register")

        db = open_db()
        try:
            svc = AuthService(db)
            try:
                user, tokens = svc.signup(
                    email=email,
                    password=password,
                    full_name=body.get("full_name"),
                    role=role,
                )
            except Exception:
                db.rollback()
                raise
            payload = {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role.value,
                    "is_verified": user.is_verified,
                },
            }
            if tokens:
                payload.update(tokens)
            else:
                payload["message"] = (
                    "Account created. Please verify your email before signing in."
                )
            return APIResponse(payload, status_code=201)
        finally:
            db.close()
    except ECBTError as exc:
        return error_response(exc)
    except Exception as exc:
        return internal_error_response(get_settings().debug, str(exc))


async def login(request: Request):
    settings = get_settings()
    ip = get_client_ip(request)
    try:
        limiter.check(client_key(ip, "login"), limit=settings.auth_rate_limit_requests,
                      window=settings.auth_rate_limit_window_seconds)
        body = await _read_json(request)
        email = body.get("email")
        password = body.get("password")
        if not email or not password or len(password) > settings.password_max_length:
            raise ValidationError("email and password are required")
        db = open_db()
        try:
            svc = AuthService(db)
            result = svc.login(email=email, password=password, ip=ip)
            return APIResponse(result)
        finally:
            db.close()
    except ECBTError as exc:
        return error_response(exc)
    except Exception as exc:
        return internal_error_response(get_settings().debug, str(exc))


async def refresh(request: Request):
    try:
        body = await _read_json(request)
        token = body.get("refresh_token")
        if not token:
            raise ValidationError("refresh_token is required")
        db = open_db()
        try:
            svc = AuthService(db)
            tokens = svc.refresh(token)
            return APIResponse(tokens)
        finally:
            db.close()
    except ECBTError as exc:
        return error_response(exc)
    except Exception as exc:
        return internal_error_response(get_settings().debug, str(exc))


async def me(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        return APIResponse({
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        })
    except ECBTError as exc:
        return error_response(exc)
    except Exception as exc:
        return internal_error_response(get_settings().debug, str(exc))
    finally:
        db.close()


async def change_password(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        body = await _read_json(request)
        current = body.get("current_password")
        new = body.get("new_password")
        if not current or not new:
            raise ValidationError("current_password and new_password are required")
        AuthService(db).change_password(user, current, new)
        return APIResponse({"message": "Password updated successfully"})
    except ECBTError as exc:
        return error_response(exc)
    except Exception as exc:
        return internal_error_response(get_settings().debug, str(exc))
    finally:
        db.close()


async def logout(request: Request):
    db = open_db()
    try:
        user = get_current_user(request, db)
        AuthService(db).logout(user)
        return APIResponse({"message": "Sessions revoked"})
    except ECBTError as exc:
        return error_response(exc)
    finally:
        db.close()


async def forgot_password(request: Request):
    settings = get_settings()
    ip = get_client_ip(request)
    try:
        limiter.check(client_key(ip, "forgot-password"), limit=settings.auth_rate_limit_requests,
                      window=settings.auth_rate_limit_window_seconds)
        body = await _read_json(request)
        email = body.get("email")
        if not email:
            raise ValidationError("email is required")
        db = open_db()
        try:
            AuthService(db).request_password_reset(email)
            # Reset tokens are never returned by the API. Deliver them through
            # a configured out-of-band email integration in the application.
            payload = {"message": "If that email exists, a reset link has been sent."}
            return APIResponse(payload)
        finally:
            db.close()
    except ECBTError as exc:
        return error_response(exc)
    except Exception as exc:
        return internal_error_response(get_settings().debug, str(exc))



async def verify_email(request: Request):
    try:
        body = await _read_json(request)
        token = body.get("token")
        if not token:
            raise ValidationError("token is required")
        db = open_db()
        try:
            user = AuthService(db).verify_email(token)
            from ecbtkit.security.tokens import create_token_pair_for_user
            tokens = create_token_pair_for_user(user)
            return APIResponse({
                **tokens,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role.value,
                    "is_verified": user.is_verified,
                },
                "message": "Email verified successfully",
            })
        finally:
            db.close()
    except ECBTError as exc:
        return error_response(exc)
    except Exception as exc:
        return internal_error_response(get_settings().debug, str(exc))


async def reset_password(request: Request):
    try:
        body = await _read_json(request)
        token = body.get("token")
        new_password = body.get("new_password")
        if not token or not new_password:
            raise ValidationError("token and new_password are required")
        if len(new_password) > get_settings().password_max_length:
            raise ValidationError("new_password is too long")
        db = open_db()
        try:
            AuthService(db).reset_password(token, new_password)
            return APIResponse({"message": "Password has been reset. You can log in now."})
        finally:
            db.close()
    except ECBTError as exc:
        return error_response(exc)
    except Exception as exc:
        return internal_error_response(get_settings().debug, str(exc))


auth_routes = [
    Route("/auth/signup", signup, methods=["POST"]),
    Route("/auth/register", signup, methods=["POST"]),  # alias
    Route("/auth/login", login, methods=["POST"]),
    Route("/auth/refresh", refresh, methods=["POST"]),
    Route("/auth/me", me, methods=["GET"]),
    Route("/auth/logout", logout, methods=["POST"]),
    Route("/auth/change-password", change_password, methods=["POST"]),
    Route("/auth/forgot-password", forgot_password, methods=["POST"]),
    Route("/auth/verify-email", verify_email, methods=["POST"]),
    Route("/auth/reset-password", reset_password, methods=["POST"]),
]
