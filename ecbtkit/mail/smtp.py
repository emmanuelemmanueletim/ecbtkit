"""Generic SMTP delivery (works with any relay: SES SMTP, SendGrid SMTP, Mailgun, Postmark, company mail)."""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from ecbtkit.mail.base import EmailMessage, EmailProvider, SendResult, _mask_email

logger = logging.getLogger("ecbtkit.mail")


class SMTPEmailProvider(EmailProvider):
    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: float = 15.0,
        default_from: Optional[str] = None,
        default_from_name: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.timeout = timeout
        self.default_from = default_from
        self.default_from_name = default_from_name

    def send(self, message: EmailMessage) -> SendResult:
        from_addr = message.from_email or self.default_from
        if not from_addr:
            return SendResult(ok=False, provider=self.name, error="from_email is not configured")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = message.subject
        msg["From"] = (
            f"{message.from_name or self.default_from_name} <{from_addr}>"
            if (message.from_name or self.default_from_name)
            else from_addr
        )
        msg["To"] = message.to
        if message.reply_to:
            msg["Reply-To"] = message.reply_to
        for k, v in message.headers.items():
            msg[k] = v

        msg.attach(MIMEText(message.text_body, "plain", "utf-8"))
        if message.html_body:
            msg.attach(MIMEText(message.html_body, "html", "utf-8"))

        try:
            if self.use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context) as server:
                    if self.username:
                        server.login(self.username, self.password or "")
                    server.sendmail(from_addr, [message.to], msg.as_string())
            else:
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                    server.ehlo()
                    if self.use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                        server.ehlo()
                    if self.username:
                        server.login(self.username, self.password or "")
                    server.sendmail(from_addr, [message.to], msg.as_string())

            logger.info("email.sent provider=smtp to=%s", _mask_email(message.to))
            return SendResult(ok=True, provider=self.name)
        except Exception as exc:
            logger.error("email.failed provider=smtp to=%s error=%s", _mask_email(message.to), type(exc).__name__)
            return SendResult(ok=False, provider=self.name, error=type(exc).__name__)
