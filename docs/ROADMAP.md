# Implementation Roadmap

Phased build of the system specified in [`REQUIREMENTS.md`](REQUIREMENTS.md).
Each phase is independently testable to 100% coverage before the next begins.
External services are behind interfaces and faked in tests throughout.

| Phase | Scope | Key requirements | Status |
|------|-------|------------------|--------|
| **0** | Project scaffold, dependency bootstrap, CI quality gates | TST-01/07 | ✅ done |
| **1** | Request **state machine** + domain vocabulary | §6, FR-CNF-04, FR-DLV-03/04, TST-04 | ✅ done |
| **2** | Domain **models** (Request, Message, Document/Revision, Client) + config layer | FR-CFG-*, §9 | ⏳ next |
| **3** | **Provider interfaces** + in-memory fakes (LLM, transcription, vision, storage, notifier, WhatsApp client) | NFR-PORT-01 | ⏳ |
| **4** | **Ingestion**: webhook verify + HMAC, payload parsing, idempotency, media download | FR-ING-*, NFR-IDEMP-01, NFR-SEC-* | ⏳ |
| **5** | **Media processing** pipeline → normalized transcript | FR-MED-* | ⏳ |
| **6** | **Aggregation** (inactivity + max-duration windows, restart-safe) | FR-AGG-* | ⏳ |
| **7** | **Classification** (versioned prompt, structured result, thresholds) | FR-CLS-* | ⏳ |
| **8** | **Notification** + HITL #1 confirmation + response correlation | FR-NOT-*, FR-CNF-* | ⏳ |
| **9** | **Generation** (intent prompts, retries, structured content) | FR-GEN-*, FR-REV-* | ⏳ |
| **10** | **Rendering** PDF + DOCX from structured content | FR-RND-* | ⏳ |
| **11** | **Delivery** + HITL #2 approval / revision loop | FR-DLV-* | ⏳ |
| **12** | **Orchestrator** wiring all stages over the state machine + persistence | §6, NFR-DURAB-01, NFR-AVAIL-01 | ⏳ |
| **13** | **API** (FastAPI webhook + async worker), local fakes E2E harness | DEP-04, TST-02/08 | ⏳ |
| **14** | **Deployment**: EC2 / systemd / S3 / Secrets Manager / CloudWatch, IaC | DEP-*, NFR-* | ⏳ |
| **15** | Observability, cost caps, retention | NFR-OBS-*, NFR-COST-01, NFR-RETN-01 | ⏳ |

## Decisions blocking later phases

The [Open Questions](REQUIREMENTS.md#16-open-questions) in the requirements —
especially **how the owner replies for HITL** (email reply vs WhatsApp reply vs
signed action links), the **WABA number**, **branding assets**, and **tax
handling** — should be resolved before Phases 8–11, which depend on them.
