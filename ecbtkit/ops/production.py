"""
Production configuration validation.

Call at startup (or via CLI) to reject unsafe deployments.
"""

from __future__ import annotations

from typing import List

from ecbtkit.core.config import Settings, get_settings


class ProductionCheckError(Exception):
    def __init__(self, problems: List[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


def validate_production_settings(settings: Settings | None = None) -> List[str]:
    """
    Return a list of problems. Empty list = safe for production.
    """
    s = settings or get_settings()
    problems: List[str] = []

    if not s.is_production:
        return problems

    if s.debug:
        problems.append("ECBT_DEBUG must be false in production")

    key = s.secret_key or ""
    if len(key) < 32 or key.startswith("INSECURE") or key.startswith("change-me"):
        problems.append("ECBT_SECRET_KEY must be a strong random secret (≥32 chars)")

    url = (s.database_url or "").lower()
    if url.startswith("sqlite"):
        problems.append("SQLite is not recommended for production — use PostgreSQL or MySQL")

    if "*" in (s.cors_origins or []) and s.cors_allow_credentials:
        problems.append("Wildcard CORS with credentials is unsafe — set explicit ECBT_CORS_ORIGINS")

    if getattr(s, "mail_enabled", False):
        if not s.mail_from:
            problems.append("ECBT_MAIL_FROM is required when email is enabled")
        if (s.mail_provider or "null") in ("null", "none", ""):
            problems.append("ECBT_MAIL_PROVIDER must be set when email is enabled")

    return problems


def assert_production_safe(settings: Settings | None = None) -> None:
    problems = validate_production_settings(settings)
    if problems:
        raise ProductionCheckError(problems)
