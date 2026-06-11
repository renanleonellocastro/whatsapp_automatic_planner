"""Parse WhatsApp Business Cloud API inbound webhook payloads (FR-ING-04).

Turns the nested ``entry[].changes[].value.messages[]`` structure into a flat
list of :class:`ParsedMessage`, enriched with the sender's wa_id and profile
name. Unsupported message types and non-message notifications (e.g. delivery
status updates) are skipped rather than crashing (FR-ING-04).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from wapp_planner.workflow.enums import MessageType

# WhatsApp ``type`` string -> our MessageType. "voice" is derived from an
# ``audio.voice`` flag, so it is not in this direct map.
_TYPE_MAP: dict[str, MessageType] = {
    "text": MessageType.TEXT,
    "audio": MessageType.AUDIO,
    "image": MessageType.IMAGE,
    "video": MessageType.VIDEO,
    "document": MessageType.DOCUMENT,
}


class ParsedMessage(BaseModel):
    """A single inbound message extracted from a webhook payload."""

    whatsapp_id: str
    sender: str
    sender_name: str | None
    type: MessageType
    timestamp: datetime
    text: str | None = None
    caption: str | None = None
    media_id: str | None = None
    mime_type: str | None = None
    filename: str | None = None


class ParseResult(BaseModel):
    """Outcome of parsing one webhook body."""

    messages: list[ParsedMessage]
    skipped_types: list[str]


def _timestamp(raw: Any) -> datetime:
    try:
        return datetime.fromtimestamp(int(raw), tz=UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


def _resolve_type(message: dict[str, Any]) -> MessageType | None:
    raw_type = message.get("type")
    if raw_type == "audio" and isinstance(message.get("audio"), dict):
        if message["audio"].get("voice") is True:
            return MessageType.VOICE
        return MessageType.AUDIO
    return _TYPE_MAP.get(raw_type) if isinstance(raw_type, str) else None


def _build_message(
    message: dict[str, Any], mtype: MessageType, contacts: dict[str, str | None]
) -> ParsedMessage:
    sender = str(message.get("from", ""))
    parsed = ParsedMessage(
        whatsapp_id=str(message["id"]),
        sender=sender,
        sender_name=contacts.get(sender),
        type=mtype,
        timestamp=_timestamp(message.get("timestamp")),
    )
    if mtype is MessageType.TEXT:
        parsed.text = (message.get("text") or {}).get("body")
        return parsed

    # Media types share an object keyed by the raw whatsapp type name.
    media_key = "audio" if mtype is MessageType.VOICE else mtype.value
    media = message.get(media_key) or {}
    parsed.caption = media.get("caption")
    parsed.media_id = media.get("id")
    parsed.mime_type = media.get("mime_type")
    parsed.filename = media.get("filename")
    return parsed


def _iter_values(payload: dict[str, Any]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value")
            if isinstance(value, dict):
                values.append(value)
    return values


def parse_webhook(payload: dict[str, Any]) -> ParseResult:
    """Parse a webhook body into supported messages plus a list of skipped types."""
    messages: list[ParsedMessage] = []
    skipped: list[str] = []

    for value in _iter_values(payload):
        contacts = {
            str(c.get("wa_id")): (c.get("profile") or {}).get("name")
            for c in value.get("contacts", [])
            if isinstance(c, dict) and c.get("wa_id") is not None
        }
        for message in value.get("messages", []):
            if not isinstance(message, dict) or "id" not in message:
                skipped.append(str(message.get("type") if isinstance(message, dict) else message))
                continue
            mtype = _resolve_type(message)
            if mtype is None:
                skipped.append(str(message.get("type")))
                continue
            messages.append(_build_message(message, mtype, contacts))

    return ParseResult(messages=messages, skipped_types=skipped)
