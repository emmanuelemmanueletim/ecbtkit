"""
eCBTKit configuration — environment-driven, production-minded.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ECBT_",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "eCBTKit"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # HTTP
    api_prefix: str = "/api/v1"
    docs_url: str = "/docs"
    host: str = "0.0.0.0"
    port: int = 8000

    # Database — supports SQLAlchemy SQL URL schemes
    # Examples:
    #   sqlite:///./ecbtkit.db
    #   postgresql://user:pass@localhost:5432/ecbt
    #   mysql+pymysql://user:pass@localhost:3306/ecbt
    database_url: str = "sqlite:///./ecbtkit.db"
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_seconds: int = 30
    database_backend: str = "auto"
    database_auto_create: bool = False

    # Security — CHANGE secret_key in production
    secret_key: str = Field(
        default="INSECURE-DEV-KEY-change-me-to-64-plus-random-chars",
        min_length=16,
    )
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    algorithm: str = "HS256"

    # Password policy
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_digit: bool = True
    password_require_special: bool = True
    password_max_length: int = 128

    # Auth lockout / brute-force
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    require_email_verification: bool = False

    # CORS
    cors_origins: List[str] = Field(default_factory=list)
    cors_allow_credentials: bool = False
    cors_allow_methods: List[str] = Field(default_factory=lambda: ["*"])
    cors_allow_headers: List[str] = Field(default_factory=lambda: ["*"])

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    auth_rate_limit_requests: int = 10
    auth_rate_limit_window_seconds: int = 60

    # ---- Email (provider-neutral) ------------------------------------
    # Set ECBT_MAIL_PROVIDER + keys — framework handles the rest.
    # Providers: null | smtp | ses | sendgrid | mailgun | postmark | resend | gmail | office365
    mail_enabled: bool = False
    mail_provider: str = "null"
    mail_from: Optional[str] = None
    mail_from_name: Optional[str] = None
    mail_host: Optional[str] = None
    mail_port: Optional[int] = None
    mail_username: Optional[str] = None
    mail_password: Optional[str] = None
    mail_api_key: Optional[str] = None  # SendGrid / Resend / etc.
    mail_region: Optional[str] = None   # SES region e.g. us-east-1
    mail_use_tls: Optional[bool] = True
    mail_use_ssl: bool = False
    mail_timeout: float = 15.0
    mail_async: bool = True  # send in background thread — never blocks signup
    mail_link_base_url: str = "http://127.0.0.1:8000"  # frontend base for reset/verify links

    # ---- Redis (shared rate limiting) --------------------------------
    redis_url: Optional[str] = None  # e.g. redis://localhost:6379/0

    # ---- Production / ops --------------------------------------------
    trusted_hosts: List[str] = Field(default_factory=list)
    force_https: bool = False
    https_enforced_at_proxy: bool = False
    trusted_proxy_hosts: List[str] = Field(default_factory=list)

    # Security headers
    security_headers_enabled: bool = True
    hsts_max_age: int = 31536000

    # Exam defaults
    default_exam_duration_minutes: int = 60
    default_pass_mark: float = 40.0

    # Logging
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def resolved_backend(self) -> str:
        if self.database_backend not in ("auto", "sql"):
            return self.database_backend
        url = self.database_url.lower()
        if url.startswith("mongodb"):
            return "mongo"
        return "sql"

    def validate(self) -> None:
        if self.resolved_backend != "sql":
            raise ValueError("The examination framework currently supports SQL backends only")
        if self.database_url.lower().startswith("sqlite") and self.is_production:
            raise ValueError("SQLite is not supported for production deployments")
        if self.is_production:
            if self.secret_key.startswith("INSECURE-") or len(self.secret_key) < 32:
                raise ValueError("ECBT_SECRET_KEY must be a strong random secret of at least 32 characters in production")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS origins are not allowed in production")

_settings_override: Settings | None = None


def set_settings(settings: Settings | None = None) -> Settings:
    """Install settings for this process (tests and app bootstrap)."""
    global _settings_override
    if settings is None:
        _settings_override = None
        return Settings()
    _settings_override = settings
    return settings


def _clear_settings_cache() -> None:
    global _settings_override
    _settings_override = None


def get_settings() -> Settings:
    global _settings_override
    if _settings_override is not None:
        return _settings_override
    _settings_override = Settings()
    return _settings_override


get_settings.cache_clear = _clear_settings_cache  # type: ignore[attr-defined]
