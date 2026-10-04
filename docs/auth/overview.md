# Authentication

eCBTKit ships a **production-oriented auth system** that is independent of any web framework.

## What stands out

| Feature | Detail |
|---------|--------|
| **Argon2id hashing** | Memory-hard password hashing (PHC winner). PBKDF2 fallback if argon2-cffi missing |
| **Password policy** | Length, upper/lower/digit/special, common-password blocklist — all configurable |
| **Account lockout** | After N failed logins, account locked for M minutes (anti brute-force) |
| **Access + refresh tokens** | Short-lived access JWT, longer-lived refresh token |
| **Password reset** | One-time token with expiry (email the token in production) |
| **Change password** | Requires current password |
| **Rate limiting** | Stricter limits on `/auth/*` endpoints |
| **Uniform login errors** | Same message for unknown email vs wrong password (no user enumeration) |
| **Timing-safe verify** | HMAC compare / Argon2 verify |
| **Hash upgrade** | Transparent rehash on login when parameters change |
| **First-admin protection** | Cannot self-register as administrator (use CLI) |
| **Email verification hook** | Optional gate via `ECBT_REQUIRE_EMAIL_VERIFICATION` |

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/signup` | No | Register (candidate/examiner) |
| POST | `/api/v1/auth/login` | No | Login → access + refresh tokens |
| POST | `/api/v1/auth/refresh` | No | Rotate tokens with refresh_token |
| GET | `/api/v1/auth/me` | Bearer | Current user profile |
| POST | `/api/v1/auth/change-password` | Bearer | Change password |
| POST | `/api/v1/auth/forgot-password` | No | Request reset token |
| POST | `/api/v1/auth/reset-password` | No | Reset with token |

## Signup body

```json
{
  "email": "student@school.edu",
  "password": "Str0ng!Pass",
  "full_name": "Ada Lovelace",
  "role": "candidate"
}
```

Password must satisfy the policy (default: 8+ chars, upper, lower, digit, special).

## Login response

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "student@school.edu",
    "full_name": "Ada Lovelace",
    "role": "candidate",
    "is_verified": true
  }
}
```

Use header: `Authorization: Bearer <access_token>`

## Configuration (`.env`)

```env
ECBT_SECRET_KEY=use-a-long-random-string-at-least-32-chars
ECBT_ACCESS_TOKEN_EXPIRE_MINUTES=30
ECBT_REFRESH_TOKEN_EXPIRE_DAYS=14
ECBT_PASSWORD_MIN_LENGTH=8
ECBT_MAX_LOGIN_ATTEMPTS=5
ECBT_LOCKOUT_DURATION_MINUTES=15
ECBT_REQUIRE_EMAIL_VERIFICATION=false
ECBT_AUTH_RATE_LIMIT_REQUESTS=10
ECBT_AUTH_RATE_LIMIT_WINDOW_SECONDS=60
```

## Programmatic use (no HTTP)

```python
from ecbtkit.auth.service import AuthService
from ecbtkit.db.base import session_scope

with session_scope() as db:
    svc = AuthService(db)
    user, tokens = svc.signup(email="a@b.com", password="Str0ng!Pass")
    result = svc.login(email="a@b.com", password="Str0ng!Pass")
```
