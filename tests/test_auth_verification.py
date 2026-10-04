"""Auth verification, reset tokens, logout, and signup-without-credentials tests."""

from __future__ import annotations

import gc
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from ecbtkit import CBT
from ecbtkit.core.config import Settings, set_settings, get_settings
from ecbtkit.db.base import get_session_factory
from ecbtkit.models.user import User
from ecbtkit.auth.service import AuthService, _hash_token
from ecbtkit.security.passwords import generate_secure_token
from ecbtkit.security.tokens import decode_token, _b64url_encode, _sign
from ecbtkit.core.exceptions import TokenInvalidError


def _make_settings(**kwargs) -> Settings:
    defaults = dict(
        _env_file=None,
        database_auto_create=True,
        mail_enabled=False,
        cors_origins=[],
        secret_key="test-secret-key-at-least-32-characters-long",
        rate_limit_enabled=False,
        require_email_verification=False,
        environment="development",
        debug=True,
    )
    defaults.update(kwargs)
    return Settings(**defaults)


class AuthVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db_path = Path(self.temp_dir.name) / "auth.db"
        self.settings = _make_settings(
            database_url=f"sqlite:///{db_path.as_posix()}",
            require_email_verification=True,
        )
        set_settings(self.settings)
        get_settings.cache_clear()
        set_settings(self.settings)

        from ecbtkit.db import base as db_base
        db_base._engine = None
        db_base._SessionLocal = None

        self.cbt = CBT(self.settings)
        self.client = TestClient(self.cbt.app)
        self.db: Session = get_session_factory()()

    def tearDown(self):
        try:
            self.db.close()
        except Exception:
            pass
        try:
            self.client.close()
        except Exception:
            pass
        from ecbtkit.db import base as db_base
        if db_base._engine is not None:
            db_base._engine.dispose()
            db_base._engine = None
            db_base._SessionLocal = None
        set_settings(None)
        get_settings.cache_clear()
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

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
        self.assertEqual(r.status_code, 401, r.text)
        self.assertEqual(r.json()["error"]["code"], "EMAIL_NOT_VERIFIED")

    def test_verify_email_valid_token(self):
        self.client.post("/api/v1/auth/signup", json={
            "email": "ok@example.test",
            "password": "StrongPass1!",
        })
        self.db.expire_all()
        user = self.db.query(User).filter_by(email="ok@example.test").one()
        raw = generate_secure_token(32)
        user.verification_token_hash = _hash_token(raw)
        user.verification_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        self.db.commit()

        r = self.client.post("/api/v1/auth/verify-email", json={"token": raw})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("access_token", r.json())
        self.assertTrue(r.json()["user"]["is_verified"])

        r2 = self.client.post("/api/v1/auth/verify-email", json={"token": raw})
        self.assertEqual(r2.status_code, 401, r2.text)

    def test_verify_expired_token(self):
        self.client.post("/api/v1/auth/signup", json={
            "email": "exp@example.test",
            "password": "StrongPass1!",
        })
        self.db.expire_all()
        user = self.db.query(User).filter_by(email="exp@example.test").one()
        raw = generate_secure_token(32)
        user.verification_token_hash = _hash_token(raw)
        user.verification_token_expires = datetime.now(timezone.utc) - timedelta(hours=1)
        self.db.commit()

        r = self.client.post("/api/v1/auth/verify-email", json={"token": raw})
        self.assertEqual(r.status_code, 401, r.text)

    def test_verify_malformed_token(self):
        r = self.client.post("/api/v1/auth/verify-email", json={"token": "short"})
        self.assertEqual(r.status_code, 401)

    def test_forgot_password_never_returns_token(self):
        self.client.post("/api/v1/auth/signup", json={
            "email": "reset@example.test",
            "password": "StrongPass1!",
        })
        self.db.expire_all()
        user = self.db.query(User).filter_by(email="reset@example.test").one()
        user.is_verified = True
        user.verification_token_hash = None
        self.db.commit()

        r = self.client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.test"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertNotIn("token", body)
        self.assertNotIn("debug_reset_token", body)
        self.db.refresh(user)
        self.assertIsNone(user.reset_token_hash)

        r2 = self.client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.test"})
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertEqual(r2.json().get("message"), body.get("message"))

    def test_logout_revokes_refresh(self):
        # Separate app with verification off
        from ecbtkit.db import base as db_base
        if db_base._engine is not None:
            db_base._engine.dispose()
            db_base._engine = None
            db_base._SessionLocal = None

        db_path = Path(self.temp_dir.name) / "logout.db"
        settings = _make_settings(
            database_url=f"sqlite:///{db_path.as_posix()}",
            require_email_verification=False,
        )
        set_settings(settings)
        get_settings.cache_clear()
        set_settings(settings)
        cbt = CBT(settings)
        client = TestClient(cbt.app)
        signup = client.post("/api/v1/auth/signup", json={
            "email": "out@example.test",
            "password": "StrongPass1!",
        })
        self.assertEqual(signup.status_code, 201, signup.text)
        tokens = signup.json()
        self.assertIn("access_token", tokens)
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        r = client.post("/api/v1/auth/logout", headers=headers)
        self.assertEqual(r.status_code, 200, r.text)

        r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        self.assertIn(r2.status_code, (401, 400), r2.text)

        client.close()
        if db_base._engine is not None:
            db_base._engine.dispose()
            db_base._engine = None
            db_base._SessionLocal = None


class ProductionRateLimitConfigTests(unittest.TestCase):
    def _safe_production_settings(self, **overrides):
        values = dict(
            environment="production",
            debug=False,
            secret_key="a" * 40,
            database_url="postgresql://u:p@localhost/db",
            rate_limit_enabled=True,
            redis_url="redis://localhost:6379/0",
            cors_origins=["https://app.example.com"],
            cors_allow_credentials=True,
            database_auto_create=False,
            mail_enabled=True,
            mail_provider="smtp",
            mail_from="noreply@example.com",
            mail_host="smtp.example.com",
            mail_link_base_url="https://app.example.com",
            trusted_hosts=["api.example.com"],
            force_https=True,
        )
        values.update(overrides)
        return _make_settings(**values)

    def test_production_requires_redis_when_rate_limit_enabled(self):
        from ecbtkit.ops.production import validate_production_settings

        s = self._safe_production_settings(redis_url=None)
        problems = validate_production_settings(s)
        self.assertTrue(any("REDIS" in p for p in problems))

    def test_production_accepts_redis_url(self):
        from ecbtkit.ops.production import validate_production_settings

        s = self._safe_production_settings()
        problems = validate_production_settings(s)
        self.assertFalse(any("REDIS" in p for p in problems))
        self.assertEqual(problems, [])

    def test_production_requires_host_and_https_settings(self):
        from ecbtkit.ops.production import validate_production_settings

        settings = self._safe_production_settings(trusted_hosts=[], force_https=False)
        problems = validate_production_settings(settings)
        self.assertTrue(any("TRUSTED_HOSTS" in item for item in problems))
        self.assertTrue(any("FORCE_HTTPS" in item for item in problems))

    def test_production_rejects_email_configuration_that_builds_null_provider(self):
        from ecbtkit.ops.production import validate_production_settings

        settings = self._safe_production_settings(mail_host=None)
        problems = validate_production_settings(settings)
        self.assertTrue(any("MAIL_HOST" in item for item in problems))

    def test_production_app_refuses_unsafe_configuration(self):
        settings = self._safe_production_settings(force_https=False)
        set_settings(settings)
        get_settings.cache_clear()
        set_settings(settings)
        with self.assertRaisesRegex(RuntimeError, "Unsafe production config"):
            CBT(settings, create_tables=False)


class TokenValidationTests(unittest.TestCase):
    def test_decode_rejects_token_without_expiry(self):
        settings = _make_settings()
        set_settings(settings)
        get_settings.cache_clear()
        set_settings(settings)
        header = _b64url_encode(b'{"alg":"HS256","typ":"JWT"}')
        body = _b64url_encode(b'{"sub":"1","type":"access"}')
        signature = _sign(f"{header}.{body}", settings.secret_key)
        with self.assertRaises(TokenInvalidError):
            decode_token(f"{header}.{body}.{signature}")


class RedisRateLimitAtomicityTests(unittest.TestCase):
    def test_redis_backend_uses_script_and_rejects_at_limit(self):
        from ecbtkit.security.rate_limit import _RedisBackend
        from ecbtkit.core.exceptions import RateLimitError

        class FakeRedis:
            script = None

            def eval(self, script, key_count, key, now, window, limit, member):
                self.script = script
                return [0, 7]

        backend = object.__new__(_RedisBackend)
        backend._r = FakeRedis()
        with self.assertRaises(RateLimitError):
            backend.check("auth:login", limit=1, window=60)
        self.assertIn("redis.call('ZCARD'", backend._r.script)
        self.assertIn("if count >= limit", backend._r.script)


class ProxyTrustTests(unittest.TestCase):
    def test_proxy_ip_must_match_trusted_network(self):
        from ecbtkit.http.deps import _is_trusted_proxy

        self.assertTrue(_is_trusted_proxy("10.1.2.3", ["10.0.0.0/8"]))
        self.assertFalse(_is_trusted_proxy("192.0.2.8", ["10.0.0.0/8"]))


if __name__ == "__main__":
    unittest.main()
