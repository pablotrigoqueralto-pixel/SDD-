"""Microsoft Graph mailer: client-credentials token + sendMail as the rep's mailbox.

Two plain HTTPS calls via httpx — the Graph SDK would be dead weight for this.
Requires application `Mail.Send` with admin consent and an application access
policy scoping it to the sales mailboxes (see development_guide.md).
"""

import base64
from typing import Any

import httpx

from app.application.quotes.mailer import MailDeliveryError
from app.domain.quotes.mail import MailRecipient

TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"  # noqa: S105 — an endpoint, not a secret
SENDMAIL_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
SCOPE = "https://graph.microsoft.com/.default"
TIMEOUT_SECONDS = 10.0


def build_message(
    *,
    recipients: list[MailRecipient],
    subject: str,
    body: str,
    attachment_name: str,
    attachment: bytes,
) -> dict[str, Any]:
    return {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [
                {
                    "emailAddress": (
                        {"address": recipient.email, "name": recipient.name}
                        if recipient.name
                        else {"address": recipient.email}
                    )
                }
                for recipient in recipients
            ],
            "attachments": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": attachment_name,
                    "contentType": "application/pdf",
                    "contentBytes": base64.b64encode(attachment).decode("ascii"),
                }
            ],
        },
        "saveToSentItems": True,
    }


class GraphMailer:
    enabled = True

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._transport = transport

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
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=self._transport) as client:
            token = await self._token(client)
            try:
                response = await client.post(
                    SENDMAIL_URL.format(sender=sender_email),
                    headers={"Authorization": f"Bearer {token}"},
                    json=build_message(
                        recipients=recipients,
                        subject=subject,
                        body=body,
                        attachment_name=attachment_name,
                        attachment=attachment,
                    ),
                )
            except httpx.HTTPError as error:
                raise MailDeliveryError(f"Graph sendMail request failed: {error}") from error
            if response.status_code != httpx.codes.ACCEPTED:
                raise MailDeliveryError(
                    f"Graph sendMail returned {response.status_code}: {response.text[:200]}"
                )

    async def _token(self, client: httpx.AsyncClient) -> str:
        try:
            response = await client.post(
                TOKEN_URL.format(tenant=self._tenant_id),
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": SCOPE,
                    "grant_type": "client_credentials",
                },
            )
        except httpx.HTTPError as error:
            raise MailDeliveryError(f"Graph token request failed: {error}") from error
        if response.status_code != httpx.codes.OK:
            raise MailDeliveryError(f"Graph token request returned {response.status_code}")
        token = response.json().get("access_token")
        if not token:
            raise MailDeliveryError("Graph token response carried no access_token")
        return str(token)


class NullMailer:
    """Mode `off`: sending is skipped and the outbox records it."""

    enabled = False

    async def send(
        self,
        *,
        sender_email: str,
        recipients: list[MailRecipient],
        subject: str,
        body: str,
        attachment_name: str,
        attachment: bytes,
    ) -> None:  # pragma: no cover — the service never calls a disabled mailer
        raise MailDeliveryError("Mail integration is disabled")
