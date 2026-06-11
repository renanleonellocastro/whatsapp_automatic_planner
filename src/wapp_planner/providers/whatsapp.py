"""WhatsApp Business Cloud API adapters (AD-1, FR-ING-07, FR-DLV-01).

* :class:`WhatsAppGraphMediaClient` downloads inbound media (two-step Graph
  call: media-id → URL → bytes).
* :class:`WhatsAppNotifier` sends an outbound text message to the owner.

Both take an injected ``httpx.Client`` so they are unit-tested with
``httpx.MockTransport`` — no network. Outbound document *uploads* over WhatsApp
are intentionally out of scope here; document delivery favors email, while the
WhatsApp message carries the body + action links.
"""

from __future__ import annotations

import httpx

from wapp_planner.domain.enums import Channel
from wapp_planner.providers.base import (
    DownloadedMedia,
    Notifier,
    OutboundMessage,
    WhatsAppMediaClient,
)

DEFAULT_API_BASE = "https://graph.facebook.com/v20.0"


class WhatsAppGraphMediaClient(WhatsAppMediaClient):
    """Downloads inbound media via the Graph API."""

    def __init__(self, http: httpx.Client, *, access_token: str, api_base: str = DEFAULT_API_BASE):
        self._http = http
        self._auth = {"Authorization": f"Bearer {access_token}"}
        self._api_base = api_base.rstrip("/")

    def download(self, media_id: str) -> DownloadedMedia:
        meta = self._http.get(f"{self._api_base}/{media_id}", headers=self._auth)
        meta.raise_for_status()
        info = meta.json()
        media = self._http.get(info["url"], headers=self._auth)
        media.raise_for_status()
        return DownloadedMedia(
            content=media.content,
            mime_type=info.get("mime_type", "application/octet-stream"),
        )


class WhatsAppNotifier(Notifier):
    """Sends a text message to the owner's WhatsApp number."""

    channel = Channel.WHATSAPP

    def __init__(
        self,
        http: httpx.Client,
        *,
        access_token: str,
        phone_number_id: str,
        api_base: str = DEFAULT_API_BASE,
    ) -> None:
        self._http = http
        self._auth = {"Authorization": f"Bearer {access_token}"}
        self._url = f"{api_base.rstrip('/')}/{phone_number_id}/messages"

    def send(self, message: OutboundMessage) -> str:
        body = message.body
        if message.attachments:
            names = ", ".join(a.filename for a in message.attachments)
            body = f"{body}\n\n(Documents sent by email: {names})"
        response = self._http.post(
            self._url,
            headers=self._auth,
            json={
                "messaging_product": "whatsapp",
                "to": message.recipient,
                "type": "text",
                "text": {"body": body},
            },
        )
        response.raise_for_status()
        message_id: str = response.json()["messages"][0]["id"]
        return message_id
