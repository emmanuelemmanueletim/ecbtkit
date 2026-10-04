"""
One-line provider setup.

    ECBT_MAIL_PROVIDER=sendgrid
    ECBT_MAIL_API_KEY=SG.xxx
    ECBT_MAIL_FROM=noreply@yourapp.com

That's enough. No custom SMTP code required.
"""

from __future__ import annotations

from typing import Optional

from ecbtkit.core.config import Settings
from ecbtkit.mail.base import EmailProvider, NullEmailProvider
from ecbtkit.mail.smtp import SMTPEmailProvider

# Well-known SMTP presets — user only picks the provider name + credentials
SMTP_PRESETS = {
    "smtp": {},  # fully custom via ECBT_MAIL_HOST / PORT / etc.
    "ses": {
        "host": "email-smtp.{region}.amazonaws.com",
        "port": 587,
        "use_tls": True,
    },
    "sendgrid": {
        "host": "smtp.sendgrid.net",
        "port": 587,
        "use_tls": True,
        "username": "apikey",  # SendGrid SMTP username is literally "apikey"
    },
    "mailgun": {
        "host": "smtp.mailgun.org",
        "port": 587,
        "use_tls": True,
    },
    "postmark": {
        "host": "smtp.postmarkapp.com",
        "port": 587,
        "use_tls": True,
    },
    "resend": {
        "host": "smtp.resend.com",
        "port": 587,
        "use_tls": True,
        "username": "resend",
    },
    "gmail": {
        "host": "smtp.gmail.com",
        "port": 587,
        "use_tls": True,
    },
    "office365": {
        "host": "smtp.office365.com",
        "port": 587,
        "use_tls": True,
    },
}


def build_email_provider(settings: Settings) -> EmailProvider:
    """Factory: settings → ready-to-use provider. Zero boilerplate for the developer."""
    provider = (settings.mail_provider or "null").strip().lower()

    if not settings.mail_enabled or provider in ("null", "none", "off", ""):
        return NullEmailProvider()

    preset = SMTP_PRESETS.get(provider)
    if preset is None and provider != "smtp":
        # Unknown name — treat as custom SMTP if host is set
        if not settings.mail_host:
            return NullEmailProvider()
        preset = {}

    # Resolve host (SES needs region)
    host = settings.mail_host or preset.get("host", "")
    if provider == "ses" and "{region}" in host:
        region = settings.mail_region or "us-east-1"
        host = host.replace("{region}", region)

    port = settings.mail_port or preset.get("port", 587)
    use_tls = settings.mail_use_tls if settings.mail_use_tls is not None else preset.get("use_tls", True)
    use_ssl = settings.mail_use_ssl

    username = settings.mail_username or preset.get("username") or settings.mail_api_key
    password = settings.mail_password or settings.mail_api_key

    # SendGrid / Resend: API key is the SMTP password
    if provider in ("sendgrid", "resend") and settings.mail_api_key:
        password = settings.mail_api_key
        if not username:
            username = preset.get("username", "apikey")

    if not host:
        return NullEmailProvider()

    return SMTPEmailProvider(
        host=host,
        port=int(port),
        username=username,
        password=password,
        use_tls=bool(use_tls),
        use_ssl=bool(use_ssl),
        timeout=float(settings.mail_timeout),
        default_from=settings.mail_from,
        default_from_name=settings.mail_from_name,
    )
