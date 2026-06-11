"""Unit tests for configuration & secrets (FR-CFG-02/03/04)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from wapp_planner.config.settings import Secrets, Settings
from wapp_planner.domain.enums import Channel

SECRET_KW = {
    "openai_api_key": "sk-x",
    "whatsapp_access_token": "t",
    "whatsapp_phone_number_id": "pid",
    "whatsapp_verify_token": "vt",
    "whatsapp_app_secret": "as",
    "smtp_host": "smtp.example.com",
    "smtp_username": "u",
    "smtp_password": "p",
}


def test_settings_email_default_requires_owner_email() -> None:
    # Defaults use EMAIL channels; without owner_email this must fail fast.
    with pytest.raises(ValidationError, match="owner_email is required"):
        Settings()


def test_settings_valid_email_config() -> None:
    s = Settings(owner_email="owner@example.com")
    assert s.notify_channel is Channel.EMAIL
    assert s.aws_region == "us-east-1"


def test_settings_whatsapp_requires_owner_whatsapp() -> None:
    with pytest.raises(ValidationError, match="owner_whatsapp is required"):
        Settings(notify_channel=Channel.WHATSAPP, deliver_channel=Channel.WHATSAPP)


def test_settings_whatsapp_valid() -> None:
    s = Settings(
        notify_channel=Channel.WHATSAPP,
        deliver_channel=Channel.WHATSAPP,
        owner_whatsapp="+15550000000",
    )
    assert s.deliver_channel is Channel.WHATSAPP


def test_settings_both_requires_both_contacts() -> None:
    with pytest.raises(ValidationError, match="owner_whatsapp is required"):
        Settings(
            notify_channel=Channel.BOTH,
            deliver_channel=Channel.BOTH,
            owner_email="owner@example.com",
        )
    s = Settings(
        notify_channel=Channel.BOTH,
        deliver_channel=Channel.BOTH,
        owner_email="owner@example.com",
        owner_whatsapp="+1",
    )
    assert s.notify_channel is Channel.BOTH


def test_settings_deliver_channel_validated_independently() -> None:
    # notify is satisfiable (email) but deliver=WHATSAPP needs owner_whatsapp.
    with pytest.raises(ValidationError, match="owner_whatsapp is required for deliver"):
        Settings(
            notify_channel=Channel.EMAIL,
            deliver_channel=Channel.WHATSAPP,
            owner_email="owner@example.com",
        )


def test_settings_window_bounds() -> None:
    with pytest.raises(ValidationError, match="must be >="):
        Settings(
            owner_email="owner@example.com",
            aggregation_inactivity_seconds=600,
            aggregation_max_duration_seconds=60,
        )


def test_settings_positive_window_enforced() -> None:
    with pytest.raises(ValidationError):
        Settings(owner_email="owner@example.com", aggregation_inactivity_seconds=0)


def test_settings_threshold_bounds() -> None:
    with pytest.raises(ValidationError):
        Settings(owner_email="owner@example.com", classification_confidence_threshold=1.5)


def test_settings_cost_caps_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(owner_email="owner@example.com", per_request_cost_cap_usd=0)


def test_settings_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WAPP_OWNER_EMAIL", "env@example.com")
    monkeypatch.setenv("WAPP_LLM_MODEL", "gpt-4o-mini")
    s = Settings()
    assert s.owner_email == "env@example.com"
    assert s.llm_model == "gpt-4o-mini"


# ── Secrets ─────────────────────────────────────────────────────────────
def test_secrets_require_all_fields() -> None:
    with pytest.raises(ValidationError):
        Secrets()


def test_secrets_valid() -> None:
    secrets = Secrets(**SECRET_KW)
    assert secrets.smtp_port == 587
    assert secrets.openai_api_key == "sk-x"


def test_secrets_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in SECRET_KW.items():
        monkeypatch.setenv(f"WAPP_SECRET_{key.upper()}", str(value))
    secrets = Secrets()
    assert secrets.whatsapp_phone_number_id == "pid"
