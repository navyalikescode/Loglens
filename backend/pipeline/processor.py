"""
Orchestrates the full LogLens analysis pipeline.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

import structlog

import prompts
from analysis.anomaly_detector import Anomaly, AnomalyDetector
from analysis.error_clusterer import ErrorCluster, ErrorClusterer
from analysis.root_cause_analyzer import RootCause, RootCauseAnalyzer
from analysis.timeline_builder import TimelineBuilder, TimelineEvent
from parsers.auto_parser import detect_and_parse
from parsers.base_parser import LogLevel, LogSource

logger = structlog.get_logger(__name__)


@dataclass
class AnalysisResult:
    log_source: LogSource
    total_lines: int
    parsed_lines: int
    skipped_lines: int
    time_range: tuple[datetime | None, datetime | None]

    anomalies: list[Anomaly] = field(default_factory=list)
    error_clusters: list[ErrorCluster] = field(default_factory=list)
    timeline: list[TimelineEvent] = field(default_factory=list)
    root_causes: list[RootCause] = field(default_factory=list)

    error_rate: float = 0.0
    warning_rate: float = 0.0
    critical_count: int = 0
    top_error_messages: list[str] = field(default_factory=list)

    processing_time_ms: float = 0.0
    pipeline_version: str = ""


class LogProcessor:
    """
    Full pipeline: parse → anomalies → clusters → timeline → root causes → stats.
    Accepts an optional progress_callback(step_name, step_index) to report progress.
    """

    def process(
        self,
        log_text: str,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> AnalysisResult:
        t0 = time.perf_counter()
        lines = log_text.splitlines()
        total_lines = len(lines)

        def _progress(step: str, idx: int):
            if progress_callback:
                progress_callback(step, idx)

        entries: list[Any] = []
        source = LogSource.UNKNOWN
        skipped = 0

        _progress("parsing", 0)
        try:
            entries, source, skipped = detect_and_parse(log_text)
            logger.info(
                "pipeline_parse_done",
                entries=len(entries),
                source=source.value,
                skipped=skipped,
            )
        except Exception:
            logger.exception("pipeline_parse_failed")
            entries, source, skipped = [], LogSource.UNKNOWN, 0

        ts_list = [e.timestamp for e in entries if e.timestamp]
        time_range: tuple[datetime | None, datetime | None] = (
            (min(ts_list) if ts_list else None),
            (max(ts_list) if ts_list else None),
        )

        anomalies: list[Anomaly] = []
        _progress("anomalies", 1)
        try:
            t1 = time.perf_counter()
            anomalies = AnomalyDetector().detect(entries)
            logger.info(
                "pipeline_anomalies_done",
                ms=(time.perf_counter() - t1) * 1000,
                count=len(anomalies),
            )
        except Exception:
            logger.exception("pipeline_anomalies_failed")

        clusters: list[ErrorCluster] = []
        _progress("clustering", 2)
        try:
            t1 = time.perf_counter()
            clusters = ErrorClusterer().cluster(entries)
            logger.info(
                "pipeline_clusters_done",
                ms=(time.perf_counter() - t1) * 1000,
                count=len(clusters),
            )
        except Exception:
            logger.exception("pipeline_clusters_failed")

        timeline: list[TimelineEvent] = []
        _progress("timeline", 3)
        try:
            t1 = time.perf_counter()
            timeline = TimelineBuilder().build(entries, anomalies)
            logger.info(
                "pipeline_timeline_done",
                ms=(time.perf_counter() - t1) * 1000,
                count=len(timeline),
            )
        except Exception:
            logger.exception("pipeline_timeline_failed")

        root_causes: list[RootCause] = []
        _progress("root_cause", 4)
        try:
            t1 = time.perf_counter()
            root_causes = RootCauseAnalyzer().analyze(entries, anomalies, clusters)
            logger.info(
                "pipeline_root_cause_done",
                ms=(time.perf_counter() - t1) * 1000,
                count=len(root_causes),
            )
        except Exception:
            logger.exception("pipeline_root_cause_failed")

        n = max(len(entries), 1)
        errs = sum(
            1
            for e in entries
            if e.level in (LogLevel.ERROR, LogLevel.CRITICAL)
        )
        warns = sum(1 for e in entries if e.level == LogLevel.WARNING)
        crit = sum(1 for e in entries if e.level == LogLevel.CRITICAL)

        from collections import Counter

        err_msgs = [
            e.message for e in entries if e.level in (LogLevel.ERROR, LogLevel.CRITICAL)
        ]
        top5 = [m for m, _ in Counter(err_msgs).most_common(5)]

        _progress("report", 5)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        return AnalysisResult(
            log_source=source,
            total_lines=total_lines,
            parsed_lines=len(entries),
            skipped_lines=skipped,
            time_range=time_range,
            anomalies=anomalies,
            error_clusters=clusters,
            timeline=timeline,
            root_causes=root_causes,
            error_rate=errs / n,
            warning_rate=warns / n,
            critical_count=crit,
            top_error_messages=top5,
            processing_time_ms=elapsed_ms,
            pipeline_version=prompts.VERSION,
        )

    async def aprocess(
        self,
        log_text: str,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> AnalysisResult:
        loop = asyncio.get_event_loop()

        if progress_callback:
            def threadsafe_cb(step: str, idx: int):
                loop.call_soon_threadsafe(progress_callback, step, idx)
            return await asyncio.to_thread(self.process, log_text, threadsafe_cb)

        return await asyncio.to_thread(self.process, log_text)
