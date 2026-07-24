"""
Simple file-based report store for shareable links.
Stores reports as JSON files in a data/reports/ directory.
"""

import json
import os
import uuid
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "data/reports"))


def _ensure_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def save_report(report_json: dict) -> str:
    _ensure_dir()
    report_id = str(uuid.uuid4())[:12]
    path = REPORTS_DIR / f"{report_id}.json"
    with open(path, "w") as f:
        json.dump(report_json, f)
    logger.info("report_saved", report_id=report_id)
    return report_id


def get_report(report_id: str) -> dict | None:
    path = REPORTS_DIR / f"{report_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def list_reports(limit: int = 50) -> list[dict]:
    _ensure_dir()
    reports = []
    for p in sorted(REPORTS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            with open(p) as f:
                data = json.load(f)
            reports.append({
                "id": p.stem,
                "severity": data.get("severity"),
                "log_source": data.get("metadata", {}).get("log_source"),
                "total_lines": data.get("metadata", {}).get("total_lines"),
                "generated_at": data.get("metadata", {}).get("generated_at"),
            })
        except Exception:
            continue
    return reports


def delete_report(report_id: str) -> bool:
    path = REPORTS_DIR / f"{report_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False
