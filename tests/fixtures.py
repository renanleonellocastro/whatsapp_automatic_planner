"""Reusable test fixtures: WhatsApp webhook payload builders (TST-03)."""

from __future__ import annotations

from typing import Any


def webhook(
    messages: list[dict[str, Any]], *, contacts: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Wrap raw message dicts in the standard Cloud API webhook envelope."""
    default_contacts = (
        contacts
        if contacts is not None
        else [{"wa_id": "15551230000", "profile": {"name": "Bob Builder"}}]
    )
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "PID"},
                            "contacts": default_contacts,
                            "messages": messages,
                        },
                    }
                ],
            }
        ],
    }


def text_message(
    body: str = "Need a quote for a kitchen remodel", *, mid: str = "wamid.text1"
) -> dict[str, Any]:
    return {
        "id": mid,
        "from": "15551230000",
        "timestamp": "1749640000",
        "type": "text",
        "text": {"body": body},
    }


def audio_message(*, voice: bool = False, mid: str = "wamid.audio1") -> dict[str, Any]:
    return {
        "id": mid,
        "from": "15551230000",
        "timestamp": "1749640001",
        "type": "audio",
        "audio": {"id": "media-audio-1", "mime_type": "audio/ogg", "voice": voice},
    }


def image_message(*, caption: str | None = "front wall", mid: str = "wamid.img1") -> dict[str, Any]:
    return {
        "id": mid,
        "from": "15551230000",
        "timestamp": "1749640002",
        "type": "image",
        "image": {"id": "media-img-1", "mime_type": "image/jpeg", "caption": caption},
    }


def document_message(*, mid: str = "wamid.doc1") -> dict[str, Any]:
    return {
        "id": mid,
        "from": "15551230000",
        "timestamp": "1749640003",
        "type": "document",
        "document": {
            "id": "media-doc-1",
            "mime_type": "application/pdf",
            "filename": "scope.pdf",
        },
    }
