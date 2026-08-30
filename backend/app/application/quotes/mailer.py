"""Outbound mailer protocol; implemented by Graph in infrastructure."""

from typing import Protocol

from app.domain.quotes.mail import MailRecipient


class MailDeliveryError(Exception):
    """Delivery failed; the caller records the outbox entry as failed."""


class QuoteMailer(Protocol):
    @property
    def enabled(self) -> bool:
        """False when no mail integration is configured (dev, E2E)."""
        ...

    async def send(
        self,
        *,
        sender_email: str,
        recipients: list[MailRecipient],
        subject: str,
        body: str,
        attachment_name: str,
        attachment: bytes,
    ) -> None:
        """Sends the message from the sender's mailbox; raises on failure."""
        ...
