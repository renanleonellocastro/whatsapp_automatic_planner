# WhatsApp Service Planner Automation

Automates the owner's manual workflow for a US civil-construction / renovation
planning business: ingest job details a client sends over **WhatsApp**
(text / audio / video / images), detect whether they're asking for a **quote**
or an **execution plan**, generate that document with an LLM, and deliver it
back — with the owner approving at two checkpoints. Runs 24/7 (AWS EC2).

> 📄 **Start here:** [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) — the
> authoritative, reviewable requirements. [`docs/ROADMAP.md`](docs/ROADMAP.md)
> tracks build phases; [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) maps each
> requirement → code → tests.

## Pipeline

```
WhatsApp inbound ─► download+transcribe media ─► aggregate ─► classify intent
   ─► notify owner ─► [HITL #1 confirm] ─► generate (OpenAI) ─► render PDF+DOCX
   ─► deliver ─► [HITL #2 approve] ─► done   (revision loop on rejection)
```

## Key facts

- **WhatsApp:** official WhatsApp Business Cloud API (Meta).
- **LLM:** OpenAI API (pay-per-use key — **not** the ChatGPT Plus subscription),
  behind a swappable provider interface.
- **Channels:** email + WhatsApp, both configurable.
- **Output:** PDF and Word (.docx), in English.

## Develop

```bash
python3 scripts/bootstrap_env.py     # create .venv and install deps (isolated)
source .venv/bin/activate
pytest --cov                          # full suite + 100% coverage gate
ruff check . && mypy                  # lint + type-check
```

The codebase uses a `src/` layout (`src/wapp_planner/`). External I/O
(WhatsApp, OpenAI, AWS, SMTP) sits behind interfaces so the whole flow runs
against fakes in tests — no real services needed.

## Status

Phases 0–13 complete and 100%-tested (342 tests, 100% line+branch coverage,
ruff + strict mypy clean). The whole system is wired and runnable: a **FastAPI**
app (webhook verify/HMAC + inbound + `/hitl/action`) with an async
aggregation-flush worker, the full pipeline (ingest → media→transcript →
aggregate → classify → notify with **signed action links** → generate → **PDF +
DOCX** → deliver → approve/revise → complete) over the persisted state machine,
and **real provider adapters** behind the interfaces — OpenAI (LLM/transcription/
vision), WhatsApp Graph, S3, SMTP/SES, ffmpeg. Run with `python -m wapp_planner`
(needs credentials). End-to-end and HTTP integration tests run entirely on fakes.

**Remaining (phases 14–15):** AWS deployment IaC (EC2/systemd/S3/Secrets
Manager/CloudWatch) and observability/cost-caps/retention. See
[`docs/ROADMAP.md`](docs/ROADMAP.md).
