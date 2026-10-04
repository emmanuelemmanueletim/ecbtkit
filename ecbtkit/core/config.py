"""
eCBTKit configuration — environment-driven, production-minded.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

try:
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

        # Database — supports sqlite, postgresql, mysql, mongodb URLs
        # Examples:
        #   sqlite:///./ecbtkit.db
        #   postgresql://user:pass@localhost:5432/ecbt
        #   mysql+pymysql://user:pass@localhost:3306/ecbt
        #   mongodb://localhost:27017/ecbt
        database_url: str = "sqlite:///./ecbtkit.db"
        database_echo: bool = False
        # For MongoDB explicitly set backend
        database_backend: str = "auto"  # auto | sql | mongo

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
        cors_origins: List[str] = Field(default_factory=lambda: ["*"])
        cors_allow_credentials: bool = True
        cors_allow_methods: List[str] = Field(default_factory=lambda: ["*"])
        cors_allow_headers: List[str] = Field(default_factory=lambda: ["*"])

        # Rate limiting
        rate_limit_enabled: bool = True
        rate_limit_requests: int = 120
        rate_limit_window_seconds: int = 60
        auth_rate_limit_requests: int = 10
        auth_rate_limit_window_seconds: int = 60

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
            if self.database_backend != "auto":
                return self.database_backend
            url = self.database_url.lower()
            if url.startswith("mongodb"):
                return "mongo"
            return "sql"

except ImportError:
    class Settings:  # type: ignore
        def __init__(self):
            g = os.getenv
            self.app_name = g("ECBT_APP_NAME", "eCBTKit")
            self.app_version = g("ECBT_APP_VERSION", "0.1.0")
            self.debug = g("ECBT_DEBUG", "false").lower() in ("1", "true")
            self.environment = g("ECBT_ENVIRONMENT", "development")
            self.api_prefix = g("ECBT_API_PREFIX", "/api/v1")
            self.docs_url = g("ECBT_DOCS_URL", "/docs")
            self.host = g("ECBT_HOST", "0.0.0.0")
            self.port = int(g("ECBT_PORT", "8000"))
            self.database_url = g("ECBT_DATABASE_URL", "sqlite:///./ecbtkit.db")
            self.database_echo = False
            self.database_backend = g("ECBT_DATABASE_BACKEND", "auto")
            self.secret_key = g("ECBT_SECRET_KEY", "INSECURE-DEV-KEY-change-me-to-64-plus-random-chars")
            self.access_token_expire_minutes = int(g("ECBT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
            self.refresh_token_expire_days = int(g("ECBT_REFRESH_TOKEN_EXPIRE_DAYS", "14"))
            self.algorithm = "HS256"
            self.password_min_length = 8
            self.password_require_uppercase = True
            self.password_require_lowercase = True
            self.password_require_digit = True
            self.password_require_special = True
            self.password_max_length = 128
            self.max_login_attempts = 5
            self.lockout_duration_minutes = 15
            self.require_email_verification = False
            cors = g("ECBT_CORS_ORIGINS", "*")
            self.cors_origins = [x.strip() for x in cors.split(",") if x.strip()]
            self.cors_allow_credentials = True
            self.cors_allow_methods = ["*"]
            self.cors_allow_headers = ["*"]
            self.rate_limit_enabled = True
            self.rate_limit_requests = 120
            self.rate_limit_window_seconds = 60
            self.auth_rate_limit_requests = 10
            self.auth_rate_limit_window_seconds = 60
            self.security_headers_enabled = True
            self.hsts_max_age = 31536000
            self.default_exam_duration_minutes = 60
            self.default_pass_mark = 40.0
            self.log_level = g("ECBT_LOG_LEVEL", "INFO")

        @property
        def is_production(self) -> bool:
            return self.environment.lower() == "production"

        @property
        def resolved_backend(self) -> str:
            if self.database_backend != "auto":
                return self.database_backend
            if self.database_url.lower().startswith("mongodb"):
                return "mongo"
            return "sql"


@lru_cache
def get_settings() -> Settings:
    return Settings()
