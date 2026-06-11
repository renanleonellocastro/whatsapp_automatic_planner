"""Process entrypoint: ``python -m wapp_planner`` (DEP-01/04).

Builds the app from environment-backed settings + secrets and the real provider
adapters, starts a background aggregation-flush worker, and serves the FastAPI
app with uvicorn. Excluded from coverage — it wires real clients and runs the
server; the wiring it calls (``build_app``) is unit-tested with fakes.
"""

from __future__ import annotations


def main() -> None:  # pragma: no cover - process entrypoint
    import threading
    import time

    import uvicorn

    from wapp_planner.api.app import AppContext
    from wapp_planner.bootstrap import FlushWorker, build_app, default_adapters
    from wapp_planner.config.settings import Secrets, Settings

    settings = Settings()
    secrets = Secrets()  # type: ignore[call-arg]  # fields are loaded from the environment
    app = build_app(settings, secrets, default_adapters(settings, secrets))

    context: AppContext = app.state.context
    worker = FlushWorker(
        context.ingestion,
        interval_seconds=min(settings.aggregation_inactivity_seconds, 30),
        sleep=time.sleep,
    )
    threading.Thread(target=worker.run, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()
