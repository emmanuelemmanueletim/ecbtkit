"""
Database layer — SQLAlchemy engine/session only.

Schema changes must go through Alembic migrations.
Startup never alters production schema.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ecbtkit.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def _normalize_url(url: str) -> str:
    u = url.strip()
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://"):]
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
    engine_options = dict(
        echo=echo,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    if not url.startswith("sqlite"):
        engine_options.update(
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout_seconds,
        )
    engine = create_engine(url, **engine_options)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def init_db(database_url: Optional[str] = None, echo: Optional[bool] = None, engine=None):
    """Bind the global engine/session factory. Does not create or alter tables."""
    global _engine, _SessionLocal
    settings = get_settings()
    if settings.resolved_backend == "mongo":
        return None
    _engine = engine or create_db_engine(database_url, echo)
    _SessionLocal = sessionmaker(
        bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False
    )
    return _engine


def configure_engine(engine, session_factory=None):
    """Allow host applications to inject their own SQLAlchemy engine."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = session_factory or sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
    )


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


def tables_exist(engine=None) -> bool:
    eng = engine or get_engine()
    if eng is None:
        return False
    return "users" in inspect(eng).get_table_names()


def create_all_tables(engine=None):
    """
    Dev-only helper. Prefer `ecbt migrate` (Alembic) for all environments.
    Does not run ad-hoc ALTER statements.
    """
    from ecbtkit.models import (  # noqa: F401
        user, candidate, question, exam, attempt, result,
    )
    eng = engine or get_engine()
    if eng is not None:
        Base.metadata.create_all(bind=eng)


def run_alembic_upgrade(revision: str = "head") -> None:
    """Apply Alembic migrations programmatically."""
    from pathlib import Path
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    settings = get_settings()
    url = _normalize_url(settings.database_url)
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, revision)
