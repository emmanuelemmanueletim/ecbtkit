"""
Provider-neutral email interface.

Configure once — the framework sends verification and reset emails for you.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ecbtkit.mail")


@dataclass
class EmailMessage:
    to: str
    subject: str
    text_body: str
    html_body: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class SendResult:
    ok: bool
    provider: str
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailProvider(ABC):
    """Implement this to add a new provider. Users only set provider + keys."""

    name: str = "base"

    @abstractmethod
    def send(self, message: EmailMessage) -> SendResult:
        ...


class NullEmailProvider(EmailProvider):
    """No-op provider for development when email is disabled."""

    name = "null"

    def send(self, message: EmailMessage) -> SendResult:
        logger.info(
            "email.skipped provider=null to=%s subject=%s",
            _mask_email(message.to),
            message.subject,
        )
        return SendResult(ok=True, provider=self.name, message_id="null")


def _mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"*@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"
