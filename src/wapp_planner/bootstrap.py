"""Composition root: wire settings + adapters into a runnable app (DEP-01/04).

``build_app`` assembles the whole system from an :class:`Adapters` bundle and is
unit-tested with fakes. ``default_adapters`` constructs the real external clients
(OpenAI, boto3, httpx, SMTP) and is excluded from coverage since it needs real
SDKs/credentials. ``FlushWorker.tick`` drives time-based aggregation flushing.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import FastAPI

from wapp_planner import clock
from wapp_planner.aggregation.aggregator import Aggregator
from wapp_planner.api.app import AppContext, create_app
from wapp_planner.config.settings import Secrets, Settings
from wapp_planner.documents.branding import Branding
from wapp_planner.documents.generator import Generator
from wapp_planner.domain.enums import Channel
from wapp_planner.domain.models import Client
from wapp_planner.hitl.dispatcher import ChannelDispatcher, ChannelTarget
from wapp_planner.hitl.service import NotificationService
from wapp_planner.hitl.tokens import TokenSigner
from wapp_planner.ingestion.client_registry import ClientRegistry
from wapp_planner.ingestion.idempotency import IdempotencyStore, InMemoryIdempotencyStore
from wapp_planner.ingestion.media_downloader import MediaDownloader
from wapp_planner.ingestion.service import IngestionService
from wapp_planner.media.extractors import DocumentTextExtractor, VideoProcessor
from wapp_planner.media.processor import MediaProcessor
from wapp_planner.nlp.classifier import Classifier
from wapp_planner.orchestrator.orchestrator import Orchestrator
from wapp_planner.persistence.repository import InMemoryRequestRepository, RequestRepository
from wapp_planner.providers.base import (
    LLMProvider,
    Notifier,
    StorageProvider,
    TranscriptionProvider,
    VisionProvider,
    WhatsAppMediaClient,
)


@dataclass
class Adapters:
    """The concrete external-service adapters the system runs against."""

    llm: LLMProvider
    transcriber: TranscriptionProvider
    vision: VisionProvider
    video: VideoProcessor
    documents: DocumentTextExtractor
    storage: StorageProvider
    media_client: WhatsAppMediaClient
    notifiers: dict[Channel, Notifier]


def _uuid_id() -> str:  # pragma: no cover - randomness, runtime only
    return uuid.uuid4().hex


def build_app(
    settings: Settings,
    secrets: Secrets,
    adapters: Adapters,
    *,
    clients: list[Client] | None = None,
    repository: RequestRepository | None = None,
    idempotency: IdempotencyStore | None = None,
    id_factory: Callable[[], str] = _uuid_id,
) -> FastAPI:
    """Assemble the FastAPI app and all services from configuration + adapters."""
    repository = repository or InMemoryRequestRepository()
    idempotency = idempotency or InMemoryIdempotencyStore()
    signer = TokenSigner(secrets.whatsapp_app_secret)

    media_processor = MediaProcessor(
        transcriber=adapters.transcriber,
        vision=adapters.vision,
        video=adapters.video,
        documents=adapters.documents,
        transcription_model=settings.transcription_model,
        vision_model=settings.vision_model,
    )
    classifier = Classifier(
        adapters.llm, model=settings.llm_model, prompt_version=settings.prompt_version
    )
    generator = Generator(
        adapters.llm, model=settings.llm_model, prompt_version=settings.prompt_version
    )

    targets: dict[Channel, ChannelTarget] = {}
    if settings.owner_email:
        targets[Channel.EMAIL] = ChannelTarget(
            notifier=adapters.notifiers[Channel.EMAIL], recipient=settings.owner_email
        )
    if settings.owner_whatsapp:
        targets[Channel.WHATSAPP] = ChannelTarget(
            notifier=adapters.notifiers[Channel.WHATSAPP], recipient=settings.owner_whatsapp
        )
    notifications = NotificationService(
        signer=signer,
        dispatcher=ChannelDispatcher(targets),
        base_url=settings.public_base_url,
        confidence_threshold=settings.classification_confidence_threshold,
        notify_channel=settings.notify_channel,
        deliver_channel=settings.deliver_channel,
    )

    orchestrator = Orchestrator(
        repository=repository,
        media_processor=media_processor,
        classifier=classifier,
        generator=generator,
        notification_service=notifications,
        storage=adapters.storage,
        branding=Branding(),
        confidence_threshold=settings.classification_confidence_threshold,
        notify_on_none=settings.notify_on_none,
    )

    aggregator = Aggregator(
        inactivity_seconds=settings.aggregation_inactivity_seconds,
        max_duration_seconds=settings.aggregation_max_duration_seconds,
        id_factory=id_factory,
    )
    downloader = MediaDownloader(
        adapters.media_client, adapters.storage, max_bytes=settings.max_media_bytes
    )
    ingestion = IngestionService(
        app_secret=secrets.whatsapp_app_secret,
        verify_token=secrets.whatsapp_verify_token,
        idempotency=idempotency,
        media_downloader=downloader,
        storage=adapters.storage,
        aggregator=aggregator,
        orchestrator=orchestrator,
        registry=ClientRegistry(clients or []),
    )
    return create_app(
        AppContext(ingestion=ingestion, notifications=notifications, orchestrator=orchestrator)
    )


class FlushWorker:
    """Periodically flushes aggregation buckets whose window has closed."""

    def __init__(
        self,
        ingestion: IngestionService,
        *,
        interval_seconds: float,
        sleep: Callable[[float], None],
        now: Callable[[], datetime] = clock.now,
    ) -> None:
        self._ingestion = ingestion
        self._interval = interval_seconds
        self._sleep = sleep
        self._now = now

    def tick(self) -> int:
        """Flush due buckets once; return the number processed."""
        return self._ingestion.flush_due(self._now())

    def run(self) -> None:  # pragma: no cover - infinite loop driven in production
        while True:
            self.tick()
            self._sleep(self._interval)


def default_adapters(
    settings: Settings, secrets: Secrets
) -> Adapters:  # pragma: no cover - real clients
    """Construct the real external adapters (needs SDKs + credentials)."""
    import boto3
    import httpx
    from openai import OpenAI

    from wapp_planner.media.adapters import (
        SimpleDocumentTextExtractor,
        SubprocessVideoProcessor,
        subprocess_runner,
    )
    from wapp_planner.providers.email_notifier import EmailNotifier, build_smtp_connect
    from wapp_planner.providers.openai_provider import (
        OpenAILLMProvider,
        OpenAITranscriptionProvider,
        OpenAIVisionProvider,
    )
    from wapp_planner.providers.s3_storage import S3Storage
    from wapp_planner.providers.whatsapp import WhatsAppGraphMediaClient, WhatsAppNotifier

    openai_client = OpenAI(api_key=secrets.openai_api_key)
    http = httpx.Client(timeout=30.0)
    return Adapters(
        llm=OpenAILLMProvider(openai_client),
        transcriber=OpenAITranscriptionProvider(openai_client),
        vision=OpenAIVisionProvider(openai_client),
        video=SubprocessVideoProcessor(subprocess_runner()),
        documents=SimpleDocumentTextExtractor(),
        storage=S3Storage(boto3.client("s3", region_name=settings.aws_region), settings.s3_bucket),
        media_client=WhatsAppGraphMediaClient(http, access_token=secrets.whatsapp_access_token),
        notifiers={
            Channel.EMAIL: EmailNotifier(
                build_smtp_connect(
                    host=secrets.smtp_host,
                    port=secrets.smtp_port,
                    username=secrets.smtp_username,
                    password=secrets.smtp_password,
                ),
                sender=secrets.smtp_username,
            ),
            Channel.WHATSAPP: WhatsAppNotifier(
                http,
                access_token=secrets.whatsapp_access_token,
                phone_number_id=secrets.whatsapp_phone_number_id,
            ),
        },
    )
