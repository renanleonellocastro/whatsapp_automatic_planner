# Traceability Matrix

Maps each requirement to the module that satisfies it and the test that proves
it (REQUIREMENTS §15). Updated as implementation proceeds; rows are added per
phase. `—` = not yet implemented.

| Requirement | Module | Test |
|-------------|--------|------|
| §6 state machine | `workflow/state_machine.py` | `tests/unit/test_state_machine.py` |
| FR-CLS-01 (intent vocabulary) | `workflow/enums.py::Intent` | `tests/unit/test_state_machine.py` |
| FR-CLS-03 (NONE → discard) | `state_machine` `CLASSIFIED_NONE` edge | `test_classified_none_is_discarded` |
| FR-CNF-04 (confirm/correct/reject) | `state_machine` AWAITING_CLASSIFICATION edges | `test_correction_is_a_self_loop`, happy/`OWNER_REJECTED` |
| FR-DLV-03 (approve → completed) | `state_machine` `OWNER_APPROVED` edge | `test_happy_path_quote_to_completed` |
| FR-DLV-04 (revision loop) | `state_machine` `OWNER_REQUESTED_REVISION` edge | `test_revision_loops_back_to_generating` |
| FR-ING-04 (message types) | `workflow/enums.py::MessageType` | covered via import/use |
| NFR-OBS-02 (fail → alertable terminal) | `state_machine` `FAIL` edges | `test_fail_reachable_from_every_non_terminal_state` |
| TST-04 (no illegal transition; terminals reachable) | `state_machine` | `test_no_undeclared_edge_is_accepted`, `test_every_terminal_state_is_reachable`, `test_terminal_states_reject_all_triggers` |
| FR-CFG-01 (client registry) | `domain/models.py::Client` | `tests/unit/test_models.py` |
| FR-CFG-02/04 (validated settings) | `config/settings.py::Settings` | `tests/unit/test_config.py` |
| FR-CFG-03 (secrets) | `config/settings.py::Secrets` | `tests/unit/test_config.py` |
| §9 (domain entities) | `domain/models.py` | `tests/unit/test_models.py` |
| NFR-PORT-01 (provider interfaces + fakes) | `providers/base.py`, `providers/fakes.py` | `tests/unit/test_providers.py` |
| FR-ING-02 (subscription verify) | `ingestion/signature.py::verify_subscription` | `tests/unit/test_signature.py` |
| FR-ING-03 (HMAC signature) | `ingestion/signature.py::is_valid_signature` | `tests/unit/test_signature.py` |
| FR-ING-04 (payload parsing) | `ingestion/parser.py::parse_webhook` | `tests/unit/test_parser.py` |
| NFR-IDEMP-01 (idempotency) | `ingestion/idempotency.py` | `tests/unit/test_idempotency.py` |
| FR-ING-07, NFR-SEC-02 (media download + safety) | `ingestion/media_downloader.py` | `tests/unit/test_media_downloader.py` |
| FR-MED-01/02/03/04 (media extraction) | `media/processor.py`, `media/extractors.py` | `tests/unit/test_media_processor.py` |
| FR-MED-06 (normalized transcript) | `media/processor.py::NormalizedTranscript` | `tests/unit/test_media_processor.py` |
| FR-MED-07 (graceful degradation) | `media/processor.py::build_transcript` | `test_provider_failure_degrades_gracefully` |
| FR-AGG-01/02/03 (windows) | `aggregation/aggregator.py::Aggregator` | `tests/unit/test_aggregator.py` |
| FR-AGG-04 (restart-safe state) | `aggregation/aggregator.py` export/load | `test_state_export_and_restore_survives_restart` |
| FR-CLS-01/02 (structured classification) | `nlp/classifier.py`, `nlp/prompts.py` | `tests/unit/test_classifier.py` |
| FR-CLS-04 (confidence threshold) | `nlp/classifier.py::is_low_confidence` | `test_is_low_confidence` |
| FR-NOT-01/02/03 (owner notification) | `hitl/service.py`, `hitl/messages.py` | `tests/unit/test_hitl_*.py` |
| FR-CNF-02/03/04 (HITL #1 confirm/correct/reject) | `orchestrator/orchestrator.py::apply_owner_action` | `tests/unit/test_orchestrator.py` |
| AD-8 (signed action links) | `hitl/tokens.py`, `hitl/messages.py` | `tests/unit/test_hitl_tokens.py` |
| FR-GEN-01..06 (generation) | `documents/generator.py`, `nlp/prompts.py` | `tests/unit/test_generator.py` |
| FR-GEN-05 (retry → FAILED) | `generator` retry loop, `orchestrator._generate_render_deliver` | `test_exhausts_attempts_*`, `test_generation_failure_marks_request_failed` |
| FR-REV-01/02 (revision loop) | `orchestrator` REVISE branch | `test_revise_regenerates_new_revision`, integration |
| FR-RND-01/02/03 (PDF+DOCX render + store) | `documents/layout.py`, `documents/renderer.py`, `orchestrator._store_artifacts` | `tests/unit/test_layout.py`, `test_renderer.py` |
| AD-9 (tax filled per quote) | `documents/content.py::QuoteContent.tax`, `layout` | `test_layout.py` |
| AD-10 (branding placeholders) | `documents/branding.py` | `test_layout.py` |
| FR-DLV-01..05 (delivery + HITL #2) | `hitl/service.py::deliver_document`, `orchestrator` | `test_orchestrator.py`, integration |
| §6 lifecycle wiring | `orchestrator/orchestrator.py`, `workflow/triggers.py` | `tests/unit/test_orchestrator.py` |
| NFR-DURAB-01 (persistence) | `persistence/repository.py` | `tests/unit/test_repository.py` |
| NFR-IDEMP-01 (owner-action dedupe) | `repository.record_interaction`, `orchestrator` | `test_duplicate_action_is_idempotent` |
| TST-02/08 (integration, faked E2E) | `orchestrator` + all services | `tests/integration/test_end_to_end.py` |
| FR-ING-01/05 (webhook endpoint) | `api/app.py` | `tests/integration/test_api.py` |
| FR-ING-08 (client resolution/flagging) | `ingestion/client_registry.py`, `ingestion/service.py` | `test_client_registry.py`, `test_ingestion_service.py` |
| DEP-04 (async worker decoupling) | `ingestion/service.py` (receive vs flush), `bootstrap.py::FlushWorker` | `test_ingestion_service.py`, `test_bootstrap.py` |
| AD-2 (OpenAI adapters) | `providers/openai_provider.py` | `tests/unit/test_openai_provider.py` |
| AD-1 (WhatsApp Graph) | `providers/whatsapp.py` | `tests/unit/test_whatsapp.py` |
| FR-ING-07/RND-03 (S3 storage) | `providers/s3_storage.py` | `tests/unit/test_s3_storage.py` |
| AD-3 (email/SMTP notifier) | `providers/email_notifier.py` | `tests/unit/test_email_notifier.py` |
| FR-MED-02/04 (ffmpeg/document adapters) | `media/adapters.py` | `tests/unit/test_media_adapters.py` |
| DEP-01 (composition root) | `bootstrap.py`, `__main__.py` | `tests/unit/test_bootstrap.py` |
| TST-01 (100% coverage gate) | `pyproject.toml [tool.coverage]` | CI `pytest --cov` |
| TST-07 (lint/format/types) | `.github/workflows/ci.yml` | CI `ruff` + `mypy` |
| _… remaining (phases 13–15: HTTP API, real adapters, deploy, observability) …_ | — | — |
