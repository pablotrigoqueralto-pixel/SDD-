"""GraphMailer request building and error mapping over a mocked transport."""

import base64
import json

import httpx
import pytest

from app.application.quotes.mailer import MailDeliveryError
from app.domain.quotes.mail import MailRecipient
from app.infrastructure.mail.graph import GraphMailer, build_message

RECIPIENTS = [MailRecipient(email="dra@tambre.es", name="Dra. Ruiz"), MailRecipient(email="x@y.z")]


def mailer(handler: object) -> GraphMailer:
    return GraphMailer(
        tenant_id="tenant-1",
        client_id="client-1",
        client_secret="secret",
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


async def send(instance: GraphMailer) -> None:
    await instance.send(
        sender_email="ana@quermed.com",
        recipients=RECIPIENTS,
        subject="Presupuesto P-2026-0001",
        body="Adjunto",
        attachment_name="P-2026-0001.pdf",
        attachment=b"%PDF fake",
    )


def test_build_message_shape() -> None:
    message = build_message(
        recipients=RECIPIENTS,
        subject="S",
        body="B",
        attachment_name="a.pdf",
        attachment=b"bytes",
    )

    to = message["message"]["toRecipients"]
    assert to[0]["emailAddress"] == {"address": "dra@tambre.es", "name": "Dra. Ruiz"}
    assert to[1]["emailAddress"] == {"address": "x@y.z"}
    attachment = message["message"]["attachments"][0]
    assert attachment["contentType"] == "application/pdf"
    assert base64.b64decode(attachment["contentBytes"]) == b"bytes"
    assert message["saveToSentItems"] is True


async def test_send_posts_token_then_mail() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if "login.microsoftonline.com" in str(request.url):
            assert "tenant-1" in str(request.url)
            content = request.content.decode()
            assert "client_credentials" in content and "client-1" in content
            return httpx.Response(200, json={"access_token": "tok-123"})
        assert str(request.url).endswith("/users/ana@quermed.com/sendMail")
        assert request.headers["Authorization"] == "Bearer tok-123"
        payload = json.loads(request.content)
        assert payload["message"]["subject"] == "Presupuesto P-2026-0001"
        return httpx.Response(202)

    await send(mailer(handler))
    assert len(calls) == 2


async def test_token_failure_maps_to_delivery_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid_client"})

    with pytest.raises(MailDeliveryError, match="token request returned 401"):
        await send(mailer(handler))


async def test_sendmail_failure_maps_to_delivery_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "login" in str(request.url):
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(500, text="boom")

    with pytest.raises(MailDeliveryError, match="returned 500"):
        await send(mailer(handler))
