"""
High-level email service for account lifecycle.

Sends verification, password-reset, and security notices.
Never logs tokens or full reset links.
"""

from __future__ import annotations

import html

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from ecbtkit.core.config import Settings, get_settings
from ecbtkit.mail.base import EmailMessage, EmailProvider, SendResult, _mask_email
from ecbtkit.mail.providers import build_email_provider

logger = logging.getLogger("ecbtkit.mail")

# Small thread pool so signup/reset is not blocked by SMTP latency
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ecbt-mail")


class EmailService:
    def __init__(self, settings: Optional[Settings] = None, provider: Optional[EmailProvider] = None):
        self.settings = settings or get_settings()
        self.provider = provider or build_email_provider(self.settings)

    # ---- Public API -------------------------------------------------------

    def send_verification(self, *, to: str, token: str, full_name: Optional[str] = None) -> SendResult:
        link = self._link("verify-email", token)
        name = html.escape(full_name or "there")
        subject = f"Verify your {self.settings.app_name} account"
        text = (
            f"Hi {name},\n\n"
            f"Please verify your email by opening this link (expires soon):\n\n"
            f"{link}\n\n"
            f"If you did not create an account, ignore this message.\n"
        )
        html_body = self._html_shell(
            title="Verify your email",
            body=f"<p>Hi {name},</p><p>Please verify your email:</p>"
                 f'<p><a href="{link}">Verify email</a></p>'
                 f"<p>If you did not sign up, you can ignore this email.</p>",
        )
        return self._dispatch(to, subject, text, html_body)

    def send_password_reset(self, *, to: str, token: str, full_name: Optional[str] = None) -> SendResult:
        link = self._link("reset-password", token)
        name = html.escape(full_name or "there")
        subject = f"Reset your {self.settings.app_name} password"
        text = (
            f"Hi {name},\n\n"
            f"We received a request to reset your password. Use this link (single-use, expires in 1 hour):\n\n"
            f"{link}\n\n"
            f"If you did not request this, ignore this email.\n"
        )
        html_body = self._html_shell(
            title="Password reset",
            body=f"<p>Hi {name},</p><p>Reset your password (link expires in 1 hour):</p>"
                 f'<p><a href="{link}">Reset password</a></p>'
                 f"<p>If you did not request this, ignore this email.</p>",
        )
        return self._dispatch(to, subject, text, html_body)

    def send_password_changed(self, *, to: str, full_name: Optional[str] = None) -> SendResult:
        name = html.escape(full_name or "there")
        subject = f"Your {self.settings.app_name} password was changed"
        text = (
            f"Hi {name},\n\n"
            f"Your password was changed successfully. "
            f"If you did not do this, reset your password immediately and contact support.\n"
        )
        html_body = self._html_shell(
            title="Password changed",
            body=f"<p>Hi {name},</p><p>Your password was changed. "
                 f"If this wasn't you, reset it immediately.</p>",
        )
        return self._dispatch(to, subject, text, html_body)

    def send_new_signin(self, *, to: str, ip: Optional[str] = None, full_name: Optional[str] = None) -> SendResult:
        name = html.escape(full_name or "there")
        where = f" from IP {ip}" if ip else ""
        subject = f"New sign-in to {self.settings.app_name}"
        text = f"Hi {name},\n\nThere was a new sign-in to your account{where}.\nIf this wasn't you, change your password.\n"
        html_body = self._html_shell(
            title="New sign-in",
            body=f"<p>Hi {name},</p><p>New sign-in detected{where}. "
                 f"If this wasn't you, change your password.</p>",
        )
        return self._dispatch(to, subject, text, html_body)

    # ---- Internals --------------------------------------------------------

    def _link(self, path: str, token: str) -> str:
        base = (self.settings.mail_link_base_url or "http://127.0.0.1:8000").rstrip("/")
        return f"{base}/{path}?token={token}"

    def _dispatch(self, to: str, subject: str, text: str, html: str) -> SendResult:
        msg = EmailMessage(
            to=to,
            subject=subject,
            text_body=text,
            html_body=html,
            from_email=self.settings.mail_from,
            from_name=self.settings.mail_from_name,
        )
        if self.settings.mail_async:
            _executor.submit(self._safe_send, msg)
            return SendResult(ok=True, provider=self.provider.name, message_id="queued")
        return self._safe_send(msg)

    def _safe_send(self, msg: EmailMessage) -> SendResult:
        try:
            return self.provider.send(msg)
        except Exception as exc:
            logger.error(
                "email.unexpected to=%s error=%s",
                _mask_email(msg.to),
                type(exc).__name__,
            )
            return SendResult(ok=False, provider=getattr(self.provider, "name", "?"), error=str(exc))

    def _html_shell(self, title: str, body: str) -> str:
        app = self.settings.app_name
        return (
            f'<!DOCTYPE html><html><body style="font-family:sans-serif;line-height:1.5">'
            f"<h2>{title}</h2>{body}"
            f'<hr><p style="color:#888;font-size:12px">{app}</p></body></html>'
        )
