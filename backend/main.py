"""LogLens FastAPI application."""

import asyncio
import json
import threading
import time
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import prompts
from config import (
    ADMIN_API_KEY,
    ASK_TIMEOUT_SECONDS,
    CORS_ORIGINS,
    GROQ_API_KEY,
    MAX_LOG_LINES,
    MAX_LOG_SIZE_MB,
    RATE_LIMIT,
)
from observability.tracing import setup_observability
from parsers.custom_parser import (
    get_custom_formats,
    register_custom_format,
    remove_custom_format,
)
from pipeline.processor import LogProcessor
from report.formatter import ReportFormatter
from report.generator import ReportGenerator
from report_store import delete_report, get_report, list_reports, save_report

logger = structlog.get_logger(__name__)

_metrics: dict[str, Any] = {
    "total_requests": 0,
    "total_processing_time_ms": 0.0,
    "format_distribution": Counter(),
}
_eval_jobs: dict[str, dict[str, Any]] = {}
_progress_queues: dict[str, asyncio.Queue] = {}


def _err_payload(code: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": code,
        "message": message,
        "prompt_version": prompts.VERSION,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_observability()
    if not GROQ_API_KEY:
        logger.warning(
            "groq_key_not_set",
            message="GROQ_API_KEY not configured. Report generation will use template fallback.",
            hint="Get a free key at console.groq.com",
        )
    if not ADMIN_API_KEY:
        logger.warning(
            "admin_key_not_set",
            message="ADMIN_API_KEY not set. Admin endpoints will return 403.",
        )
    logger.info("loglens_ready", prompt_version=prompts.VERSION)
    yield


app = FastAPI(
    title="LogLens",
    description="AI-powered log analysis and incident report generation",
    version="2.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics/prometheus", include_in_schema=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/")
async def root():
    """Railway/edge checks often hit `/`; return 200 so the proxy does not see a failed upstream."""
    return {"service": "loglens", "ok": True}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "groq_configured": bool(GROQ_API_KEY),
        "prompt_version": prompts.VERSION,
        "report_mode": "llm" if GROQ_API_KEY else "template",
    }


async def _run_analysis(text: str, request_id: str | None = None):
    """Shared analysis logic used by both /api/analyse and /api/analyse-stream."""
    processor = LogProcessor()
    generator = ReportGenerator()
    formatter = ReportFormatter()

    queue = _progress_queues.get(request_id) if request_id else None

    def progress_cb(step: str, index: int):
        if queue:
            try:
                queue.put_nowait({"step": step, "index": index})
            except Exception:
                pass

    try:
        result = await asyncio.wait_for(
            processor.aprocess(text, progress_callback=progress_cb),
            timeout=ASK_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return None, "timeout"

    report_markdown = generator.generate(result)
    report_json = formatter.to_json(report_markdown, result)
    report_json["prompt_version"] = prompts.VERSION
    return report_json, result


@app.post("/api/analyse")
@limiter.limit(RATE_LIMIT)
async def analyse_logs(
    request: Request,
    log_text: str | None = Form(None),
    log_file: UploadFile | None = File(None),
):
    if log_file is None and not log_text:
        raise HTTPException(
            status_code=422,
            detail=_err_payload("no_input", "Provide log_text or log_file"),
        )

    t_req = time.perf_counter()
    try:
        text = await _extract_text(log_text, log_file)

        report_json, result = await _run_analysis(text)
        if result == "timeout":
            return JSONResponse(
                status_code=504,
                content=_err_payload(
                    "timeout",
                    f"Analysis timed out after {ASK_TIMEOUT_SECONDS}s. Try a smaller log file.",
                ),
            )

        elapsed = (time.perf_counter() - t_req) * 1000
        _metrics["total_requests"] += 1
        _metrics["total_processing_time_ms"] += elapsed
        _metrics["format_distribution"][result.log_source.value] += 1

        logger.info(
            "analysis_complete",
            log_source=result.log_source.value,
            total_lines=result.total_lines,
            anomaly_count=len(result.anomalies),
            cluster_count=len(result.error_clusters),
            severity=report_json["severity"],
        )

        return JSONResponse(content=report_json)

    except HTTPException:
        raise
    except Exception:
        logger.exception("analysis_failed")
        return JSONResponse(
            status_code=500,
            content=_err_payload(
                "analysis_failed",
                "Log analysis failed. Check server logs for details.",
            ),
        )


@app.post("/api/analyse-stream")
@limiter.limit(RATE_LIMIT)
async def analyse_stream(
    request: Request,
    log_text: str | None = Form(None),
    log_file: UploadFile | None = File(None),
):
    """SSE endpoint that streams real pipeline progress then returns the full result."""
    if log_file is None and not log_text:
        raise HTTPException(
            status_code=422,
            detail=_err_payload("no_input", "Provide log_text or log_file"),
        )

    text = await _extract_text(log_text, log_file)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    queue: asyncio.Queue = asyncio.Queue()
    _progress_queues[request_id] = queue

    async def event_generator():
        t_req = time.perf_counter()
        task = asyncio.create_task(_run_analysis(text, request_id))

        try:
            while not task.done():
                try:
                    progress = await asyncio.wait_for(queue.get(), timeout=0.3)
                    yield f"data: {json.dumps({'type': 'progress', **progress})}\n\n"
                except asyncio.TimeoutError:
                    continue

            report_json, result = task.result()
            if result == "timeout":
                yield f"data: {json.dumps({'type': 'error', 'message': 'Analysis timed out'})}\n\n"
            else:
                elapsed = (time.perf_counter() - t_req) * 1000
                _metrics["total_requests"] += 1
                _metrics["total_processing_time_ms"] += elapsed
                _metrics["format_distribution"][result.log_source.value] += 1
                yield f"data: {json.dumps({'type': 'complete', 'result': report_json})}\n\n"
        except Exception as e:
            logger.exception("stream_analysis_failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            _progress_queues.pop(request_id, None)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def _extract_text(log_text: str | None, log_file: UploadFile | None) -> str:
    if log_file is not None:
        content_bytes = await log_file.read()
        if len(content_bytes) > MAX_LOG_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=_err_payload("file_too_large", f"Max file size is {MAX_LOG_SIZE_MB}MB"),
            )
        text = content_bytes.decode("utf-8", errors="replace")
    else:
        text = log_text or ""

    line_count = text.count("\n")
    if line_count > MAX_LOG_LINES:
        raise HTTPException(
            status_code=422,
            detail=_err_payload("too_many_lines", f"Max {MAX_LOG_LINES} lines. Got {line_count}."),
        )
    return text


# ── Shareable Reports ─────────────────────────────────────────────────────

@app.post("/api/reports")
async def share_report(request: Request):
    """Save a report for sharing. Accepts the full report JSON body."""
    body = await request.json()
    report_id = save_report(body)
    return {"ok": True, "report_id": report_id}


@app.get("/api/reports/{report_id}")
async def get_shared_report(report_id: str):
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.get("/api/reports")
async def list_shared_reports():
    return {"reports": list_reports()}


@app.delete("/api/reports/{report_id}")
async def delete_shared_report(report_id: str):
    if delete_report(report_id):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Report not found")


# ── Custom Log Formats ────────────────────────────────────────────────────

@app.post("/api/formats/custom")
async def add_custom_format(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    pattern = body.get("pattern", "").strip()
    description = body.get("description", "")

    if not name or not pattern:
        raise HTTPException(
            status_code=422,
            detail=_err_payload("invalid_input", "Both 'name' and 'pattern' are required."),
        )

    try:
        fmt = register_custom_format(name, pattern, description)
        return {"ok": True, "format": fmt}
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=_err_payload("invalid_pattern", str(e)),
        )


@app.get("/api/formats/custom")
async def list_custom_formats():
    return {"formats": get_custom_formats()}


@app.delete("/api/formats/custom/{name}")
async def delete_custom_format(name: str):
    if remove_custom_format(name):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Custom format not found")


# ── Existing endpoints ────────────────────────────────────────────────────

@app.get("/api/formats")
async def supported_formats():
    custom = get_custom_formats()
    return {
        "formats": ["nginx", "python", "docker", "kubernetes", "systemd"]
        + [f["name"] for f in custom],
        "custom_formats": custom,
        "note": "Auto-detection tries all formats. Unknown formats use generic parser. Custom formats can be added via POST /api/formats/custom.",
    }


@app.get("/api/metrics")
async def metrics():
    n = max(_metrics["total_requests"], 1)
    return {
        "total_requests": _metrics["total_requests"],
        "avg_processing_time_ms": _metrics["total_processing_time_ms"] / n,
        "format_distribution": dict(_metrics["format_distribution"]),
        "prompt_version": prompts.VERSION,
    }


def _require_admin(request: Request) -> None:
    admin_key = request.headers.get("X-Admin-Key")
    if not ADMIN_API_KEY or admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


@app.post("/api/admin/run-evals")
async def run_evals(request: Request):
    _require_admin(request)
    job_id = str(uuid.uuid4())
    _eval_jobs[job_id] = {"status": "running", "result": None}

    def _run() -> None:
        try:
            from evals.eval_pipeline import run_eval_sync

            _eval_jobs[job_id]["result"] = run_eval_sync()
            _eval_jobs[job_id]["status"] = "done"
        except Exception as e:
            logger.exception("eval_job_failed", job_id=job_id)
            _eval_jobs[job_id]["status"] = "failed"
            _eval_jobs[job_id]["result"] = {"error": str(e)}

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id, "status": "started", "prompt_version": prompts.VERSION}


@app.get("/api/admin/eval-results/{job_id}")
async def get_eval_results(job_id: str, request: Request):
    _require_admin(request)
    job = _eval_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return {
        "job_id": job_id,
        "status": job["status"],
        "result": job["result"],
        "prompt_version": prompts.VERSION,
    }
