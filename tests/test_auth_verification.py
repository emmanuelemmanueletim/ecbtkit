"""Auth verification, reset tokens, logout, and signup-without-credentials tests."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from ecbtkit import CBT
from ecbtkit.core.config import Settings
from ecbtkit.db.base import get_session_factory
from ecbtkit.models.user import User
from ecbtkit.auth.service import AuthService, _hash_token
from ecbtkit.security.passwords import generate_secure_token


class AuthVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "auth.db"
        self.settings = Settings(
            _env_file=None,
            database_url=f"sqlite:///{db_path.as_posix()}",
            database_auto_create=True,
            require_email_verification=True,
            mail_enabled=False,
            cors_origins=[],
            secret_key="test-secret-key-at-least-32-characters-long",
        )
        self.cbt = CBT(self.settings)
        self.client = TestClient(self.cbt.app)
        self.db: Session = get_session_factory()()

    def tearDown(self):
        self.db.close()
        from ecbtkit.db import base
        if base._engine:
            base._engine.dispose()
        self.temp_dir.cleanup()

    def test_signup_without_tokens_when_verification_required(self):
        r = self.client.post("/api/v1/auth/signup", json={
            "email": "new@example.test",
            "password": "StrongPass1!",
            "full_name": "New User",
        })
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertNotIn("access_token", body)
        self.assertFalse(body["user"]["is_verified"])
        self.assertIn("verify", body.get("message", "").lower())

    def test_login_blocked_until_verified(self):
        self.client.post("/api/v1/auth/signup", json={
            "email": "block@example.test",
            "password": "StrongPass1!",
        })
        r = self.client.post("/api/v1/auth/login", json={
            "email": "block@example.test",
            "password": "StrongPass1!",
        })
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["error"]["code"], "EMAIL_NOT_VERIFIED")

    def test_verify_email_valid_token(self):
        self.client.post("/api/v1/auth/signup", json={
            "email": "ok@example.test",
            "password": "StrongPass1!",
        })
        user = self.db.query(User).filter_by(email="ok@example.test").one()
        raw = generate_secure_token(32)
        user.verification_token_hash = _hash_token(raw)
        user.verification_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        self.db.commit()

        r = self.client.post("/api/v1/auth/verify-email", json={"token": raw})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("access_token", r.json())
        self.assertTrue(r.json()["user"]["is_verified"])

        # reuse fails
        r2 = self.client.post("/api/v1/auth/verify-email", json={"token": raw})
        self.assertEqual(r2.status_code, 401)

    def test_verify_expired_token(self):
        self.client.post("/api/v1/auth/signup", json={
            "email": "exp@example.test",
            "password": "StrongPass1!",
        })
        user = self.db.query(User).filter_by(email="exp@example.test").one()
        raw = generate_secure_token(32)
        user.verification_token_hash = _hash_token(raw)
        user.verification_token_expires = datetime.now(timezone.utc) - timedelta(hours=1)
        self.db.commit()

        r = self.client.post("/api/v1/auth/verify-email", json={"token": raw})
        self.assertEqual(r.status_code, 401)

    def test_verify_malformed_token(self):
        r = self.client.post("/api/v1/auth/verify-email", json={"token": "short"})
        self.assertEqual(r.status_code, 401)

    def test_forgot_password_never_returns_token(self):
        self.client.post("/api/v1/auth/signup", json={
            "email": "reset@example.test",
            "password": "StrongPass1!",
        })
        # verify first so account is usable
        user = self.db.query(User).filter_by(email="reset@example.test").one()
        user.is_verified = True
        user.verification_token_hash = None
        self.db.commit()

        r = self.client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.test"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertNotIn("token", body)
        self.assertNotIn("debug_reset_token", body)

        # unknown email — same generic response
        r2 = self.client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.test"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json().get("message"), body.get("message"))

    def test_logout_revokes_refresh(self):
        settings = Settings(
            _env_file=None,
            database_url=self.settings.database_url,
            database_auto_create=True,
            require_email_verification=False,
            mail_enabled=False,
            cors_origins=[],
            secret_key="test-secret-key-at-least-32-characters-long",
        )
        from ecbtkit.core.config import get_settings
        get_settings.cache_clear()
        cbt = CBT(settings)
        client = TestClient(cbt.app)
        signup = client.post("/api/v1/auth/signup", json={
            "email": "out@example.test",
            "password": "StrongPass1!",
        })
        self.assertEqual(signup.status_code, 201, signup.text)
        tokens = signup.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        r = client.post("/api/v1/auth/logout", headers=headers)
        self.assertEqual(r.status_code, 200, r.text)

        # refresh should fail after logout
        r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        self.assertIn(r2.status_code, (401, 400))


class ProductionRateLimitConfigTests(unittest.TestCase):
    def test_production_requires_redis_when_rate_limit_enabled(self):
        from ecbtkit.ops.production import validate_production_settings

        s = Settings(
            _env_file=None,
            environment="production",
            debug=False,
            secret_key="a" * 40,
            database_url="postgresql://u:p@localhost/db",
            rate_limit_enabled=True,
            redis_url=None,
            cors_origins=["https://app.example.com"],
            cors_allow_credentials=True,
            database_auto_create=False,
            mail_enabled=False,
        )
        problems = validate_production_settings(s)
        self.assertTrue(any("REDIS" in p for p in problems))

    def test_production_accepts_redis_url(self):
        from ecbtkit.ops.production import validate_production_settings

        s = Settings(
            _env_file=None,
            environment="production",
            debug=False,
            secret_key="a" * 40,
            database_url="postgresql://u:p@localhost/db",
            rate_limit_enabled=True,
            redis_url="redis://localhost:6379/0",
            cors_origins=["https://app.example.com"],
            cors_allow_credentials=True,
            database_auto_create=False,
            mail_enabled=False,
        )
        problems = validate_production_settings(s)
        self.assertFalse(any("REDIS" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
