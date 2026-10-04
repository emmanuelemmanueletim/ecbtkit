"""
MongoDB adapter (optional).

Install: pip install pymongo
Configure: ECBT_DATABASE_URL=mongodb://localhost:27017/ecbt

This adapter stores documents in collections that mirror the domain models.
The SQL path remains the default for relational integrity (attempts, FK rules).
Use Mongo when your deployment prefers document storage for questions/results.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ecbtkit.core.config import get_settings

_client = None
_db = None


def get_mongo_db():
    global _client, _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise RuntimeError(
            "pymongo is required for MongoDB. Install with: pip install pymongo"
        ) from exc

    settings = get_settings()
    url = settings.database_url
    _client = MongoClient(url, serverSelectionTimeoutMS=5000)
    # database name from path or default
    db_name = url.rsplit("/", 1)[-1] or "ecbtkit"
    if "?" in db_name:
        db_name = db_name.split("?")[0]
    _db = _client[db_name]
    return _db


def mongo_health() -> Dict[str, Any]:
    try:
        db = get_mongo_db()
        db.command("ping")
        return {"status": "ok", "backend": "mongo"}
    except Exception as exc:
        return {"status": "error", "backend": "mongo", "detail": str(exc)}
