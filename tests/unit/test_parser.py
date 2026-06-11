"""Unit tests for the WhatsApp webhook parser (FR-ING-04)."""

from __future__ import annotations

from datetime import UTC, datetime

from tests import fixtures as fx
from wapp_planner.ingestion.parser import parse_webhook
from wapp_planner.workflow.enums import MessageType


def test_parse_text_message() -> None:
    result = parse_webhook(fx.webhook([fx.text_message("hello")]))
    assert len(result.messages) == 1
    msg = result.messages[0]
    assert msg.type is MessageType.TEXT
    assert msg.text == "hello"
    assert msg.sender == "15551230000"
    assert msg.sender_name == "Bob Builder"
    assert msg.timestamp == datetime(2025, 6, 11, 11, 6, 40, tzinfo=UTC)
    assert result.skipped_types == []


def test_parse_voice_vs_audio() -> None:
    voice = parse_webhook(fx.webhook([fx.audio_message(voice=True)])).messages[0]
    audio = parse_webhook(fx.webhook([fx.audio_message(voice=False)])).messages[0]
    assert voice.type is MessageType.VOICE
    assert audio.type is MessageType.AUDIO
    assert voice.media_id == "media-audio-1"
    assert voice.mime_type == "audio/ogg"


def test_parse_audio_without_audio_object_defaults_to_audio() -> None:
    raw = {"id": "m", "from": "1", "timestamp": "1", "type": "audio"}
    msg = parse_webhook(fx.webhook([raw])).messages[0]
    assert msg.type is MessageType.AUDIO
    assert msg.media_id is None


def test_parse_image_with_caption() -> None:
    msg = parse_webhook(fx.webhook([fx.image_message(caption="north wall")])).messages[0]
    assert msg.type is MessageType.IMAGE
    assert msg.caption == "north wall"
    assert msg.media_id == "media-img-1"


def test_parse_document_with_filename() -> None:
    msg = parse_webhook(fx.webhook([fx.document_message()])).messages[0]
    assert msg.type is MessageType.DOCUMENT
    assert msg.filename == "scope.pdf"
    assert msg.mime_type == "application/pdf"


def test_unsupported_type_is_skipped() -> None:
    sticker = {"id": "m", "from": "1", "timestamp": "1", "type": "sticker"}
    result = parse_webhook(fx.webhook([sticker]))
    assert result.messages == []
    assert result.skipped_types == ["sticker"]


def test_non_string_type_is_skipped() -> None:
    weird = {"id": "m", "from": "1", "timestamp": "1", "type": None}
    result = parse_webhook(fx.webhook([weird]))
    assert result.skipped_types == ["None"]


def test_message_without_id_is_skipped() -> None:
    result = parse_webhook(fx.webhook([{"type": "text", "text": {"body": "x"}}]))
    assert result.messages == []
    assert result.skipped_types == ["text"]


def test_non_dict_message_is_skipped() -> None:
    result = parse_webhook(fx.webhook(["not-a-dict"]))  # type: ignore[list-item]
    assert result.messages == []
    assert result.skipped_types == ["not-a-dict"]


def test_unknown_sender_has_no_name() -> None:
    msg_raw = fx.text_message()
    msg_raw["from"] = "99999999999"
    msg = parse_webhook(fx.webhook([msg_raw])).messages[0]
    assert msg.sender_name is None


def test_contacts_without_wa_id_are_ignored() -> None:
    payload = fx.webhook([fx.text_message()], contacts=[{"profile": {"name": "x"}}])
    msg = parse_webhook(payload).messages[0]
    assert msg.sender_name is None


def test_invalid_timestamp_falls_back_to_now() -> None:
    raw = fx.text_message()
    raw["timestamp"] = "not-a-number"
    before = datetime.now(UTC)
    msg = parse_webhook(fx.webhook([raw])).messages[0]
    assert msg.timestamp >= before


def test_missing_timestamp_falls_back_to_now() -> None:
    raw = fx.text_message()
    del raw["timestamp"]
    before = datetime.now(UTC)
    msg = parse_webhook(fx.webhook([raw])).messages[0]
    assert msg.timestamp >= before


def test_status_only_payload_yields_no_messages() -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "x", "changes": [{"field": "messages", "value": {"statuses": []}}]}],
    }
    result = parse_webhook(payload)
    assert result.messages == []
    assert result.skipped_types == []


def test_value_not_dict_is_ignored() -> None:
    payload = {"entry": [{"changes": [{"value": "garbage"}, {}]}]}
    result = parse_webhook(payload)
    assert result.messages == []


def test_empty_payload() -> None:
    assert parse_webhook({}).messages == []


def test_multiple_messages_preserve_order() -> None:
    payload = fx.webhook([fx.text_message("one", mid="a"), fx.text_message("two", mid="b")])
    result = parse_webhook(payload)
    assert [m.whatsapp_id for m in result.messages] == ["a", "b"]
