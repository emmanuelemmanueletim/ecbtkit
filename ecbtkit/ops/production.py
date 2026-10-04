"""Production configuration validation — fail fast on unsafe settings."""

from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlparse

from ecbtkit.core.config import Settings, get_settings


class ProductionCheckError(Exception):
    def __init__(self, problems: List[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


def validate_production_settings(settings: Optional[Settings] = None) -> List[str]:
    s = settings or get_settings()
    problems: List[str] = []
    if not s.is_production:
        return problems

    if s.debug:
        problems.append("ECBT_DEBUG must be false in production")

    key = s.secret_key or ""
    if len(key) < 32 or any(
        key.lower().startswith(p) for p in ("insecure", "change-me", "secret", "password")
    ):
        problems.append("ECBT_SECRET_KEY must be a strong random secret (≥32 characters)")

    url = (s.database_url or "").lower()
    if url.startswith("sqlite"):
        problems.append("SQLite is not supported in production — use PostgreSQL or MySQL")

    if "*" in (s.cors_origins or []) and s.cors_allow_credentials:
        problems.append("Wildcard CORS with credentials is unsafe — set explicit origins")

    if s.rate_limit_enabled and not getattr(s, "redis_url", None):
        problems.append("ECBT_REDIS_URL is required in production when rate limiting is enabled")

    if getattr(s, "mail_enabled", False):
        if not s.mail_from:
            problems.append("ECBT_MAIL_FROM is required when email is enabled")
        if (s.mail_provider or "null").lower() in ("null", "none", ""):
            problems.append("ECBT_MAIL_PROVIDER must be set when email is enabled")
        base = getattr(s, "mail_link_base_url", "") or ""
        parsed = urlparse(base)
        if parsed.scheme != "https":
            problems.append("ECBT_MAIL_LINK_BASE_URL must use https in production")

    if getattr(s, "database_auto_create", False):
        problems.append("ECBT_DATABASE_AUTO_CREATE must be false in production — use Alembic")

    return problems


def assert_production_safe(settings: Optional[Settings] = None) -> None:
    problems = validate_production_settings(settings)
    if problems:
        raise ProductionCheckError(problems)
