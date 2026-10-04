"""
Database layer — SQL (SQLite / PostgreSQL / MySQL) via SQLAlchemy.

The examination framework supports SQL databases only.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy import inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ecbtkit.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def _normalize_url(url: str) -> str:
    """Accept common URL forms and map to SQLAlchemy dialects."""
    u = url.strip()
    # postgres:// → postgresql://
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://"):]
    # mysql:// → mysql+pymysql://
    if u.startswith("mysql://") and "+pymysql" not in u and "+mysqldb" not in u:
        u = "mysql+pymysql://" + u[len("mysql://"):]
    return u


def create_db_engine(database_url: Optional[str] = None, echo: Optional[bool] = None):
    settings = get_settings()
    url = _normalize_url(database_url or settings.database_url)
    echo = echo if echo is not None else settings.database_echo

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        url,
        echo=echo,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def init_db(database_url: Optional[str] = None, echo: Optional[bool] = None):
    global _engine, _SessionLocal
    settings = get_settings()
    if settings.resolved_backend != "sql":
        raise ValueError("Only SQL database backends are supported by the examination framework")
    _engine = create_db_engine(database_url, echo)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False)
    return _engine


def get_engine():
    global _engine
    if _engine is None:
        init_db()
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        init_db()
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_tables(engine=None):
    from ecbtkit.models import (  # noqa: F401
        user, candidate, question, exam, attempt, result,
    )
    eng = engine or get_engine()
    if eng is not None:
        Base.metadata.create_all(bind=eng)
        _apply_builtin_migrations(eng)


def _apply_builtin_migrations(engine) -> None:
    """Apply additive, idempotent upgrades needed by pre-migration installs."""
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("users")}
        with engine.begin() as connection:
            if "refresh_token_jti" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN refresh_token_jti VARCHAR(64)"))
            if "token_version" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"))
            if "reset_token_hash" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN reset_token_hash VARCHAR(64)"))
                if "reset_token" in columns:
                    rows = connection.execute(text("SELECT id, reset_token FROM users WHERE reset_token IS NOT NULL")).all()
                    import hashlib
                    for user_id, reset_token in rows:
                        token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()
                        connection.execute(
                            text("UPDATE users SET reset_token_hash = :token_hash, reset_token = NULL WHERE id = :user_id"),
                            {"token_hash": token_hash, "user_id": user_id},
                        )
    if "attempts" in inspector.get_table_names():
        with engine.begin() as connection:
            if engine.dialect.name == "sqlite":
                connection.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_attempt_one_active_per_candidate_exam "
                    "ON attempts (exam_id, candidate_id) WHERE status = 'ACTIVE'"
                ))
            elif engine.dialect.name == "postgresql":
                connection.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_attempt_one_active_per_candidate_exam "
                    "ON attempts (exam_id, candidate_id) WHERE status = 'ACTIVE'"
                ))
