# Requirements — WhatsApp Service Planner Automation

> **Status:** Draft v0.1 — for review
> **Owner:** Vitor Castro
> **Last updated:** 2026-06-11
> **Audience:** company employees + engineering. Open to revision via PR.

> _This document is written in English so the whole (US-based) team can review it
> and because the artifacts the system produces are in English. A Portuguese
> translation can be produced on request._

---

## 1. Purpose & Background

The company plans the stages of civil construction / renovation work in the United
States. Clients send the details of a job they will perform for **their** customers
over **WhatsApp** — sometimes as a video, sometimes as an audio note, sometimes as a
sequence of text messages, audio notes and photos, or any combination.

Today the owner does this **manually**: reads/listens to the WhatsApp content,
copies it into ChatGPT, and asks it to produce one of two documents:

1. **Quote / Budget (`QUOTE`)** — a detailed cost estimate, **written in English**,
   for the client to forward to their own customer.
2. **Execution Plan (`EXECUTION_PLAN`)** — a detailed, **step-by-step** document
   describing exactly how each part of the service should be executed.

This project automates that workflow end-to-end: ingest the WhatsApp content,
detect which of the two documents is being requested, keep a human in the loop for
two approvals, generate the document with an LLM, render it (PDF + Word) and deliver
it back — running **24/7** in the cloud (AWS EC2).

---

## 2. Glossary

| Term | Meaning |
|------|---------|
| **Owner / Operator** | The single human user (you) who reviews requests and approves output. |
| **Client** | One of your customers who sends jobs over WhatsApp. |
| **End customer** | The client's customer — the final recipient of a quote. |
| **Request** | A logical unit of work: one client's batch of related WhatsApp messages that asks for one document. |
| **Intent** | The detected type of request: `QUOTE`, `EXECUTION_PLAN`, or `NONE`. |
| **HITL** | Human-in-the-loop — a point where the system pauses for owner approval. |
| **Aggregation window** | The time window used to group a client's consecutive messages into one Request. |
| **WABA** | WhatsApp Business Account (Meta). |

---

## 3. Actors

- **Client** — sends WhatsApp messages (inbound only; never interacts with the system directly).
- **Owner** — receives notifications, confirms classification, approves/rejects documents, requests revisions. The only human decision-maker.
- **System** — this application.
- **External services** — WhatsApp Business Cloud API (Meta), OpenAI API, SMTP/email provider.

---

## 4. Locked Architecture Decisions

These were confirmed with the owner and constrain the design:

| # | Decision | Choice | Notes |
|---|----------|--------|-------|
| AD-1 | WhatsApp integration | **WhatsApp Business Cloud API (Meta)** | Official, ToS-compliant. Requires a WhatsApp Business Account, a dedicated phone number, and a verified Meta app. A personal number cannot be used as-is. |
| AD-2 | LLM provider | **OpenAI API** (pay-per-use API key) | **A ChatGPT Plus subscription does NOT grant API access** — a separate, usage-billed OpenAI API key is required. The LLM layer is abstracted (`LLMProvider` interface) so Anthropic/Claude can be added later. |
| AD-3 | Notification + delivery channels | **Email and WhatsApp, both configurable from day one** | A `channel` config selects the active channel per purpose (notify / deliver). |
| AD-4 | Output document format | **PDF and Word (.docx)** | Both generated from the same structured content. |
| AD-5 | Language of generated docs | **English** | Both QUOTE and EXECUTION_PLAN are produced in English. |
| AD-6 | Deployment target | **AWS EC2, 24/7** | Single long-running service. State persisted so restarts are safe. |
| AD-7 | Implementation language | **Python 3.12** | With 100% unit-test line+branch coverage and integration tests (see §13). |

---

## 5. High-Level Flow

```
                ┌─────────────────────────────────────────────────────────┐
                │                  WhatsApp (client)                       │
                └───────────────┬─────────────────────────────────────────┘
                                │ inbound webhook (text/audio/video/image)
                                ▼
   (1) Ingest ──► (2) Download media ──► (3) Transcribe / describe media
                                │
                                ▼
   (4) Aggregate consecutive messages from same client into one Request
                                │
                                ▼
   (5) Classify intent: QUOTE | EXECUTION_PLAN | NONE
                                │  (if NONE → ignore / log)
                                ▼
   (6) Notify owner: "New <intent> request from <client>"  ──► HITL #1
                                │  owner confirms / corrects / rejects
                                ▼
   (7) Generate document via OpenAI (QUOTE in English | EXECUTION_PLAN)
                                │
                                ▼
   (8) Render PDF + DOCX
                                │
                                ▼
   (9) Deliver document to owner, ask for approval         ──► HITL #2
                                │
                ┌───────────────┴───────────────┐
        approved │                               │ revision requested (+ feedback)
                 ▼                               ▼
        (10) COMPLETED                  (7) Regenerate with feedback ──► loop
```

---

## 6. Request State Machine

Each Request is persisted and moves through this state machine. Restarts must
resume from the persisted state.

```
RECEIVED
   └─► AGGREGATING ──(window closes)──► PROCESSING_MEDIA
                                            └─► CLASSIFYING
                                                   ├─(NONE)──► DISCARDED  (terminal)
                                                   └─► AWAITING_CLASSIFICATION
                                                          ├─(owner rejects)──► DISCARDED (terminal)
                                                          ├─(owner corrects intent)──► AWAITING_CLASSIFICATION (re-notified)
                                                          └─(owner confirms)──► GENERATING
                                                                                   └─► RENDERING
                                                                                          └─► AWAITING_APPROVAL
                                                                                                 ├─(approved)──► COMPLETED (terminal)
                                                                                                 └─(revision + feedback)──► GENERATING (loop)
FAILED  ◄── (any state, on unrecoverable error)   (terminal, alertable)
```

Allowed transitions are enforced in code; any other transition is a bug and must raise.

---

## 7. Functional Requirements

IDs are stable; reference them in code, tests and PRs (traceability — §15).

### 7.1 Ingestion (WhatsApp inbound)

- **FR-ING-01** The system SHALL expose an HTTPS webhook that receives WhatsApp Business Cloud API inbound message notifications.
- **FR-ING-02** The system SHALL verify the webhook on registration (Meta `hub.challenge`/verify-token handshake) and reject mismatched verify tokens.
- **FR-ING-03** Every inbound webhook SHALL have its payload signature validated (`X-Hub-Signature-256` HMAC-SHA256 against the app secret); invalid signatures SHALL be rejected with HTTP 403 and logged.
- **FR-ING-04** The system SHALL accept and parse these message types: `text`, `audio`, `voice`, `video`, `image`, `document`. Unsupported types SHALL be logged and skipped (not crash).
- **FR-ING-05** The system SHALL respond to the webhook within the provider timeout (acknowledge fast, process asynchronously).
- **FR-ING-06** Inbound webhook delivery is at-least-once; the system SHALL be **idempotent** per WhatsApp message id (duplicate deliveries processed once — FR-NFR-IDEMP).
- **FR-ING-07** For media messages, the system SHALL download the media bytes from the Graph API using the media id and store them in object storage (S3) keyed by request + message id.
- **FR-ING-08** The system SHALL identify the sending **client** from the WhatsApp phone number, resolving it against the client registry (§7.11). Unknown numbers SHALL still create a Request but be flagged `unknown_client`.

### 7.2 Media processing

- **FR-MED-01** Audio / voice messages SHALL be transcribed to text (speech-to-text, e.g. OpenAI Whisper / `gpt-4o-transcribe`). Source language auto-detected; transcript retained verbatim.
- **FR-MED-02** Video messages SHALL have (a) their audio track extracted and transcribed, and (b) representative key frames sampled and described via a vision model.
- **FR-MED-03** Image messages SHALL be described via a vision model; any embedded caption SHALL be preserved.
- **FR-MED-04** Document attachments (PDF/text) SHALL have their text extracted when feasible.
- **FR-MED-05** Text messages SHALL be used verbatim.
- **FR-MED-06** All extracted content SHALL be combined into a single, ordered, timestamped **normalized transcript** per Request, preserving message order and labeling each segment by source type (text/audio/video-audio/video-frame/image/document).
- **FR-MED-07** Media-processing failures (corrupt file, model error) SHALL degrade gracefully: the segment is marked `[unprocessable: <reason>]` and the Request continues; the failure is logged and surfaced in the owner notification.

### 7.3 Aggregation

- **FR-AGG-01** Consecutive messages from the same client SHALL be grouped into one Request using a configurable **inactivity window** (default 90s; configurable).
- **FR-AGG-02** A new message from a client that arrives after the window has closed SHALL start a new Request.
- **FR-AGG-03** The aggregation window SHALL be bounded by a maximum total duration (default 10 min) to prevent a never-closing Request.
- **FR-AGG-04** Aggregation state SHALL survive restarts (persisted, with timers reconstructable).

### 7.4 Classification

- **FR-CLS-01** The system SHALL classify each aggregated Request's normalized transcript into exactly one intent: `QUOTE`, `EXECUTION_PLAN`, or `NONE`.
- **FR-CLS-02** Classification SHALL use the LLM with a deterministic, versioned prompt and SHALL return a structured result: `{intent, confidence, rationale}`.
- **FR-CLS-03** `NONE` (greetings, chit-chat, unrelated content) SHALL transition the Request to `DISCARDED` without notifying the owner, unless `notify_on_none` config is enabled.
- **FR-CLS-04** Classification confidence below a configurable threshold SHALL still notify the owner but flag the result as `low_confidence`.

### 7.5 Owner notification

- **FR-NOT-01** On a successful (`QUOTE`/`EXECUTION_PLAN`) classification, the system SHALL notify the owner via the configured `notify` channel (email and/or WhatsApp).
- **FR-NOT-02** The notification SHALL include: the detected **intent**, the **client** name/number, a short summary of the request, the classification confidence/flags, and a unique Request reference.
- **FR-NOT-03** The notification SHALL tell the owner how to respond for HITL #1 (confirm / correct intent / reject) — see §7.6.

### 7.6 HITL #1 — Classification confirmation

- **FR-CNF-01** Before any document is generated, the system SHALL require the owner to confirm the detected intent.
- **FR-CNF-02** The owner SHALL be able to: **confirm**, **correct** the intent (e.g. "this is an execution plan, not a quote"), or **reject** (discard the request).
- **FR-CNF-03** The owner's response SHALL be accepted via the configured channel (reply to the notification email, or a WhatsApp reply to the system number) and correlated to the Request via its reference.
- **FR-CNF-04** A confirmation SHALL transition `AWAITING_CLASSIFICATION → GENERATING`; a correction SHALL update the intent and re-notify; a rejection SHALL transition to `DISCARDED`.
- **FR-CNF-05** Confirmations for an unknown/closed Request reference SHALL be ignored with a logged warning.

### 7.7 Document generation

- **FR-GEN-01** On confirmation, the system SHALL request the LLM to produce the document matching the confirmed intent.
- **FR-GEN-02** `QUOTE` documents SHALL be **detailed cost estimates written in English**, suitable to forward to an end customer (line items, scope, assumptions, exclusions, totals — exact template in §11).
- **FR-GEN-03** `EXECUTION_PLAN` documents SHALL be detailed, **step-by-step**, covering each phase of the service from preparation to completion.
- **FR-GEN-04** Generation SHALL use intent-specific, versioned prompt templates, fed with the normalized transcript and client metadata.
- **FR-GEN-05** Generation SHALL be retried on transient LLM errors (bounded retries with backoff); a persistent failure transitions the Request to `FAILED` and alerts the owner.
- **FR-GEN-06** The generated content SHALL be returned in a structured form (sections/line-items) to enable consistent PDF + DOCX rendering, not just free text.

### 7.8 Rendering

- **FR-RND-01** The system SHALL render the generated document to **PDF** and **Word (.docx)** from the same structured content.
- **FR-RND-02** Documents SHALL use a company-branded template (logo/header/footer placeholders, configurable).
- **FR-RND-03** Rendered artifacts SHALL be stored (S3) and associated with the Request and revision number.

### 7.9 HITL #2 — Document delivery & approval

- **FR-DLV-01** The system SHALL deliver the rendered document(s) to the owner via the configured `deliver` channel, and ask whether the owner approves.
- **FR-DLV-02** The owner SHALL be able to **approve** or **request a revision with free-text feedback**.
- **FR-DLV-03** Approval SHALL transition the Request to `COMPLETED` (terminal); the run ends.
- **FR-DLV-04** A revision request SHALL feed the owner's feedback back into generation (FR-GEN), producing a new revision, re-rendered and re-delivered. This loop SHALL be unbounded but every revision is versioned and logged.
- **FR-DLV-05** Each delivery SHALL state the Request reference and revision number and how to approve / request revision.

### 7.10 Revision loop

- **FR-REV-01** Every regeneration SHALL increment a revision counter and persist the feedback that produced it.
- **FR-REV-02** Prior revisions and their feedback SHALL be retained and provided to the LLM as context so the model improves rather than restarts.

### 7.11 Client registry & configuration

- **FR-CFG-01** A client registry SHALL map WhatsApp phone numbers to client names and optional metadata (preferred language for transcript, default company branding).
- **FR-CFG-02** All operational settings SHALL be configurable without code changes (file/env/SSM): aggregation windows, channels per purpose, confidence thresholds, prompt template versions, owner contact details, branding.
- **FR-CFG-03** Secrets (OpenAI key, WhatsApp tokens, SMTP creds, app secret) SHALL come from a secret store (AWS Secrets Manager / SSM), never committed.
- **FR-CFG-04** Configuration SHALL be validated at startup; invalid config SHALL fail fast with a clear error.

---

## 8. Non-Functional Requirements

- **NFR-AVAIL-01 (24/7)** The service SHALL run continuously and recover automatically after a crash/restart (systemd / process manager), resuming in-flight Requests from persisted state.
- **NFR-IDEMP-01 (Idempotency)** Inbound message processing, owner responses, and outbound sends SHALL be idempotent (dedupe by WhatsApp message id / response id) so retries never double-process or double-send.
- **NFR-DURAB-01 (Durability)** Request state and artifacts SHALL be persisted (DB + object storage); no in-flight Request is lost on restart.
- **NFR-SEC-01 (Security)** Webhook signatures verified (FR-ING-03); secrets in a secret store; least-privilege IAM; TLS everywhere; PII (phone numbers, client content) access-logged.
- **NFR-SEC-02** Inbound media SHALL be size/type-validated before download/processing; reject oversized or disallowed types.
- **NFR-OBS-01 (Observability)** Structured logging with a Request correlation id across every stage; key counters/metrics (requests by intent, HITL latency, LLM cost/tokens, failures) emitted (CloudWatch).
- **NFR-OBS-02** `FAILED` Requests and processing errors SHALL raise an owner-visible alert.
- **NFR-COST-01 (Cost control)** LLM and transcription usage SHALL be logged per Request (tokens, model, estimated cost); a configurable per-Request and daily spend cap SHALL be enforceable.
- **NFR-PERF-01** From window-close to owner notification SHOULD typically complete within ~60s for a normal-sized request (excludes large video transcription).
- **NFR-RETN-01 (Data retention)** Raw media, transcripts and documents SHALL have a configurable retention/TTL policy; deletion SHALL be supported (privacy).
- **NFR-RATE-01** Outbound WhatsApp/email sends SHALL respect provider rate limits with backoff.
- **NFR-PORT-01 (Portability)** The LLM, STT, notification and storage layers SHALL be behind interfaces so providers can be swapped (e.g. OpenAI→Anthropic) and so the system runs locally with fakes for tests.

---

## 9. Data Model (logical)

- **Client**: `id, phone_number(s), name, metadata, branding_profile`.
- **Request**: `id (reference), client_id, state, intent, confidence, created_at, updated_at, normalized_transcript, current_revision, flags[]`.
- **Message**: `id (whatsapp id), request_id, type, raw_ref(S3), text/transcript, order, received_at, processing_status`.
- **Document / Revision**: `id, request_id, revision_no, structured_content, pdf_ref(S3), docx_ref(S3), feedback (that produced it), llm_meta(model, tokens, cost), created_at`.
- **OwnerInteraction**: `id, request_id, kind(classification|approval), channel, raw_response, decision, received_at` — supports idempotency & audit.
- **EventLog / audit**: append-only state transitions per Request.

---

## 10. External Integrations & Contracts

| Integration | Direction | Notes |
|-------------|-----------|-------|
| WhatsApp Business Cloud API | in (webhook) + out (send message/media) | Webhook verify + HMAC signature; Graph API for media download and outbound messages; access token + phone-number-id. |
| OpenAI API | out | Chat/Responses for classification + generation; Whisper/`gpt-4o-transcribe` for STT; vision model for images/video frames. Behind `LLMProvider` / `TranscriptionProvider` / `VisionProvider` interfaces. |
| SMTP / email provider (e.g. SES) | out + in (replies) | Owner notification & delivery; reply correlation for HITL responses. |
| AWS S3 | out | Media + rendered artifact storage. |
| AWS Secrets Manager / SSM | in | Secrets & config. |
| AWS CloudWatch | out | Logs, metrics, alarms. |

---

## 11. Document Templates (to be refined with owner)

Initial structured schema; exact wording iterated during build.

**QUOTE** sections: Header (company/client/end-customer, date, quote #) · Project scope summary · Line items (description, qty, unit, unit price, total) · Subtotal/tax/total · Assumptions · Exclusions · Validity & terms · Notes.

**EXECUTION_PLAN** sections: Header · Project overview · Materials & tools · Sequential phases (each: objective, step-by-step actions, safety/code notes, dependencies, est. duration) · Quality checkpoints · Cleanup & handover · Notes.

---

## 12. Deployment (AWS)

- **DEP-01** Single long-running Python service on **EC2**, started under systemd (auto-restart).
- **DEP-02** Public HTTPS endpoint for the WhatsApp webhook (ALB or Caddy/Nginx + TLS cert).
- **DEP-03** S3 bucket for media/artifacts; Secrets Manager/SSM for secrets; CloudWatch for logs/metrics/alarms.
- **DEP-04** Async processing (background worker/queue) decoupled from the webhook responder so the webhook always acks fast.
- **DEP-05** Infrastructure reproducible (Terraform or documented IaC) — to be detailed in a deployment doc.
- **DEP-06** Configurable region; default `us-east-1` (US-based).

---

## 13. Testing & Quality Requirements

- **TST-01** **100% unit-test coverage** (line **and** branch) of the application code, enforced in CI (`pytest --cov` with `fail_under=100`). External I/O is behind interfaces and faked in unit tests.
- **TST-02** **Integration tests** for: webhook signature/verify handshake, end-to-end Request lifecycle through the state machine (with fake providers), media-processing pipeline, rendering (PDF+DOCX produced and openable), and HITL response correlation.
- **TST-03** Contract tests / fixtures for each external provider payload (WhatsApp webhook samples, OpenAI responses) so parsing is pinned.
- **TST-04** State-machine property tests: no illegal transition is ever allowed; every terminal state is reachable; resume-from-persisted-state works.
- **TST-05** Idempotency tests: duplicate webhook / duplicate owner response processed once.
- **TST-06** Failure-injection tests: provider errors → graceful degradation / `FAILED` + alert.
- **TST-07** Static quality gates in CI: formatting, linting, type-checking (`ruff`, `mypy`), and the full test suite must pass.
- **TST-08** A local end-to-end harness with **all external services faked** so the full flow is demonstrable without real WhatsApp/OpenAI/AWS.

---

## 14. Out of Scope (initial)

- Multi-operator / role-based access (single owner for now).
- Direct two-way conversation with the end customer.
- Automated sending of the final document to the end customer (owner forwards it).
- Billing/invoicing, CRM, scheduling.
- Mobile/desktop UI (interaction is via WhatsApp/email).
- Languages other than English for generated documents.

---

## 15. Traceability

Each requirement ID (FR-*/NFR-*/TST-*/DEP-*) SHALL be referenced by the code module
and tests that satisfy it (docstring tag or test id). A traceability matrix
(`docs/TRACEABILITY.md`) SHALL be maintained mapping requirement → module → test as
implementation proceeds.

---

## 16. Open Questions

1. **Owner response channel mechanics:** for HITL replies, do we prefer (a) email reply parsing, (b) WhatsApp reply to the system number, or (c) simple signed action links/commands? Affects FR-CNF-03 / FR-DLV-02.
2. **WABA number:** is a dedicated business number available, or does onboarding the current number to WhatsApp Business need to be planned?
3. **Branding assets:** logo / company details / quote terms for the templates.
4. **Tax handling in quotes:** fixed rate, per-state, or owner fills in?
5. **Spend caps:** desired per-request / daily ceilings (NFR-COST-01).
6. **Retention period** for media/transcripts/documents (NFR-RETN-01).

---

_Changelog_
- v0.1 (2026-06-11) — initial draft from owner brief + locked decisions AD-1..AD-7.
