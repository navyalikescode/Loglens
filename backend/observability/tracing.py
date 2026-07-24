"""
Arize Phoenix (OTLP) local observability + structlog.
Phoenix UI is expected at PHOENIX_OTLP_ENDPOINT (default localhost:PHOENIX_PORT).
Run `docker compose up phoenix` or the Phoenix container to collect traces.
"""

import threading

import structlog

from config import PHOENIX_PORT, SKIP_PHOENIX

logger = structlog.get_logger(__name__)


def setup_observability() -> None:
    _setup_structlog()
    if not SKIP_PHOENIX:
        _setup_phoenix()


def _setup_structlog() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def _setup_phoenix() -> None:
    """
    Register OTLP export to Phoenix and instrument LangChain in a daemon thread
    so startup is non-blocking.
    """

    def _start() -> None:
        try:
            import os

            from openinference.instrumentation.langchain import LangChainInstrumentor
            from phoenix.otel import register

            endpoint = os.getenv(
                "PHOENIX_OTLP_ENDPOINT",
                f"http://127.0.0.1:{PHOENIX_PORT}/v1/traces",
            )
            tracer_provider = register(
                endpoint=endpoint,
                protocol="http/protobuf",
                set_global_tracer_provider=True,
            )
            LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
            structlog.get_logger(__name__).info(
                "phoenix_otel_configured",
                endpoint=endpoint,
                ui_hint=f"http://127.0.0.1:{PHOENIX_PORT}",
            )
        except Exception as e:
            structlog.get_logger(__name__).warning("phoenix_start_failed", error=str(e))

    thread = threading.Thread(target=_start, daemon=True)
    thread.start()
