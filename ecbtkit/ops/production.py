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

    if "*" in (s.cors_origins or []):
        problems.append("Wildcard CORS origins are not allowed in production")
    if "*" in (s.cors_origins or []) and s.cors_allow_credentials:
        problems.append("Wildcard CORS with credentials is unsafe — set explicit origins")

    if s.rate_limit_enabled and not getattr(s, "redis_url", None):
        problems.append("ECBT_REDIS_URL is required in production when rate limiting is enabled")

    if not s.mail_enabled:
        problems.append("ECBT_MAIL_ENABLED must be true in production for account recovery")
    if s.mail_enabled:
        provider = (s.mail_provider or "null").strip().lower()
        if not s.mail_from:
            problems.append("ECBT_MAIL_FROM is required when email is enabled")
        if provider in ("null", "none", "", "off"):
            problems.append("ECBT_MAIL_PROVIDER must be set when email is enabled")
        if provider == "smtp" and not s.mail_host:
            problems.append("ECBT_MAIL_HOST is required for the smtp provider")
        if provider in {"sendgrid", "resend"} and not (s.mail_api_key or (s.mail_username and s.mail_password)):
            problems.append(f"SMTP credentials or ECBT_MAIL_API_KEY are required for {provider}")
        if provider in {"ses", "mailgun", "postmark", "gmail", "office365"}:
            has_credentials = bool((s.mail_username and s.mail_password) or s.mail_api_key)
            if not has_credentials:
                problems.append(f"SMTP credentials are required for the {provider} provider")
        base = getattr(s, "mail_link_base_url", "") or ""
        parsed = urlparse(base)
        if parsed.scheme != "https":
            problems.append("ECBT_MAIL_LINK_BASE_URL must use https in production")
    if s.access_token_expire_minutes > 30:
        problems.append("ECBT_ACCESS_TOKEN_EXPIRE_MINUTES must be 30 or less in production")
    if s.database_echo:
        problems.append("ECBT_DATABASE_ECHO must be false in production")
    if s.database_pool_size < 1 or s.database_max_overflow < 0 or s.database_pool_timeout_seconds < 1:
        problems.append("Database pool settings must use positive pool size/timeout and non-negative overflow")
    if not s.trusted_hosts:
        problems.append("ECBT_TRUSTED_HOSTS must list public hostnames in production")
    if not s.force_https and not s.https_enforced_at_proxy:
        problems.append("Enable ECBT_FORCE_HTTPS or attest HTTPS enforcement at the trusted proxy")
    if s.trusted_proxy_hosts and not s.trusted_hosts:
        problems.append("ECBT_TRUSTED_HOSTS must be set when configuring trusted proxies")

    if getattr(s, "database_auto_create", False):
        problems.append("ECBT_DATABASE_AUTO_CREATE must be false in production — use Alembic")

    return problems


def assert_production_safe(settings: Optional[Settings] = None) -> None:
    problems = validate_production_settings(settings)
    if problems:
        raise ProductionCheckError(problems)
