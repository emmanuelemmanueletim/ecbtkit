"""
Security response headers for production hardening.
"""

from __future__ import annotations

from typing import Dict

from ecbtkit.core.config import get_settings


def security_headers() -> Dict[str, str]:
    settings = get_settings()
    if not settings.security_headers_enabled:
        return {}
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "0",  # modern browsers use CSP
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "Cache-Control": "no-store",
    }
    if settings.is_production:
        headers["Strict-Transport-Security"] = (
            f"max-age={settings.hsts_max_age}; includeSubDomains; preload"
        )
    return headers
