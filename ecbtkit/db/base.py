"""
Database layer — SQL (SQLite / PostgreSQL / MySQL) via SQLAlchemy.

MongoDB is available through ecbtkit.adapters.mongo when configured.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
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
    if settings.resolved_backend == "mongo":
        # SQL engine not used for primary store
        return None
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
