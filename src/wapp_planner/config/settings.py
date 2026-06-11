"""Application configuration and secrets (REQUIREMENTS FR-CFG-02/03/04).

Operational settings come from env/file with the ``WAPP_`` prefix; secrets come
from the ``WAPP_SECRET_`` prefix (in production, populated from AWS Secrets
Manager / SSM — never committed). Config is validated on construction so an
invalid deployment fails fast with a clear error (FR-CFG-04).
"""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from wapp_planner.domain.enums import Channel


class Settings(BaseSettings):
    """Operational settings — safe to commit defaults, no secrets here."""

    model_config = SettingsConfigDict(env_prefix="WAPP_", extra="ignore")

    # Aggregation windows (FR-AGG-01/03)
    aggregation_inactivity_seconds: int = Field(default=90, gt=0)
    aggregation_max_duration_seconds: int = Field(default=600, gt=0)

    # Classification (FR-CLS-02/04)
    classification_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    notify_on_none: bool = False

    # Channels (AD-3, FR-NOT-01, FR-DLV-01)
    notify_channel: Channel = Channel.EMAIL
    deliver_channel: Channel = Channel.EMAIL

    # Owner contact details (required for whichever channels are configured)
    owner_email: str | None = None
    owner_whatsapp: str | None = None

    # LLM / media models (AD-2, FR-MED-01/02/03)
    llm_model: str = "gpt-4o"
    transcription_model: str = "gpt-4o-transcribe"
    vision_model: str = "gpt-4o"
    prompt_version: str = "v1"

    # Cost control (NFR-COST-01)
    per_request_cost_cap_usd: float | None = Field(default=None, gt=0)
    daily_cost_cap_usd: float | None = Field(default=None, gt=0)

    # Media safety (NFR-SEC-02)
    max_media_bytes: int = Field(default=50 * 1024 * 1024, gt=0)

    # Retention & deployment (NFR-RETN-01, DEP-06)
    retention_days: int = Field(default=90, gt=0)
    aws_region: str = "us-east-1"

    @model_validator(mode="after")
    def _validate_windows_and_contacts(self) -> Settings:
        if self.aggregation_max_duration_seconds < self.aggregation_inactivity_seconds:
            raise ValueError(
                "aggregation_max_duration_seconds must be >= "
                "aggregation_inactivity_seconds"
            )
        for purpose, channel in (
            ("notify", self.notify_channel),
            ("deliver", self.deliver_channel),
        ):
            if channel.includes(Channel.EMAIL) and not self.owner_email:
                raise ValueError(f"owner_email is required for {purpose} channel {channel.value!r}")
            if channel.includes(Channel.WHATSAPP) and not self.owner_whatsapp:
                raise ValueError(
                    f"owner_whatsapp is required for {purpose} channel {channel.value!r}"
                )
        return self


class Secrets(BaseSettings):
    """Secret material (FR-CFG-03). Required — construction fails if absent."""

    model_config = SettingsConfigDict(env_prefix="WAPP_SECRET_", extra="ignore")

    openai_api_key: str
    whatsapp_access_token: str
    whatsapp_phone_number_id: str
    whatsapp_verify_token: str
    whatsapp_app_secret: str
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
