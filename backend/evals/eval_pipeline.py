"""
Evaluates LogLens analysis quality against the eval dataset.
CLI: uv run python -m evals.eval_pipeline
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog

import config
from pipeline.processor import LogProcessor

logger = structlog.get_logger(__name__)

_ROOT = Path(__file__).resolve().parent
_DATASET = _ROOT / "eval_dataset.json"
_RESULTS_DIR = Path(__file__).resolve().parents[1] / "data" / "eval_results"


def run_eval_sync() -> dict:
    """Run eval synchronously; return summary metrics dict."""
    if not _DATASET.is_file():
        raise FileNotFoundError(f"Missing {_DATASET}")

    with open(_DATASET, encoding="utf-8") as f:
        cases: list[dict] = json.load(f)

    cases = cases[: config.MAX_EVAL_ROWS]
    processor = LogProcessor()

    source_ok = 0
    anomaly_hits = 0
    anomaly_total = 0
    rc_ok = 0
    sev_ok = 0
    cluster_ok = 0
    fp = 0
    times: list[float] = []

    rows_out: list[dict] = []

    for case in cases:
        cid = case["id"]
        t0 = time.perf_counter()
        result = processor.process(case["log_text"])
        elapsed = (time.perf_counter() - t0) * 1000
        times.append(elapsed)

        exp_src = case["expected_log_source"]
        if result.log_source.value == exp_src:
            source_ok += 1

        exp_an = set(case.get("expected_anomaly_types", []))
        got_an = {a.anomaly_type for a in result.anomalies}
        if exp_an:
            anomaly_total += len(exp_an)
            anomaly_hits += len(exp_an & got_an)

        exp_rc = case["expected_root_cause_category"]
        got_rc = {r.category for r in result.root_causes}
        if exp_rc in got_rc:
            rc_ok += 1

        from report.formatter import ReportFormatter

        sev = ReportFormatter().infer_severity(result)
        if sev == case["expected_severity"]:
            sev_ok += 1

        if len(result.error_clusters) >= case.get("expected_min_clusters", 0):
            cluster_ok += 1

        if case.get("expect_no_anomalies"):
            if result.anomalies:
                fp += 1

        rows_out.append(
            {
                "id": cid,
                "elapsed_ms": elapsed,
                "log_source": result.log_source.value,
                "severity": sev,
                "anomaly_types": list(got_an),
                "root_categories": list(got_rc),
            }
        )

    n = max(len(cases), 1)
    summary = {
        "cases": len(cases),
        "log_source_accuracy": source_ok / n,
        "anomaly_type_recall": anomaly_hits / max(anomaly_total, 1),
        "root_cause_category_accuracy": rc_ok / n,
        "severity_accuracy": sev_ok / n,
        "cluster_detection_rate": cluster_ok / n,
        "false_positive_rate": fp / n,
        "avg_processing_time_ms": sum(times) / max(len(times), 1),
        "rows": rows_out,
    }

    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = _RESULTS_DIR / f"eval_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "cases": cases}, f, indent=2)

    logger.info("eval_saved", path=str(out_path))
    return summary


def main() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
    s = run_eval_sync()
    log = structlog.get_logger(__name__)
    log.info(
        "eval_summary_table",
        log_source_accuracy=f"{s['log_source_accuracy']:.2%}",
        anomaly_type_recall=f"{s['anomaly_type_recall']:.2%}",
        root_cause_category_accuracy=f"{s['root_cause_category_accuracy']:.2%}",
        severity_accuracy=f"{s['severity_accuracy']:.2%}",
        cluster_detection_rate=f"{s['cluster_detection_rate']:.2%}",
        false_positive_rate=f"{s['false_positive_rate']:.2%}",
        avg_processing_time_ms=f"{s['avg_processing_time_ms']:.1f}",
    )


if __name__ == "__main__":
    main()
