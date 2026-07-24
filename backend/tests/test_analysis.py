from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np

import config
from analysis.anomaly_detector import AnomalyDetector
from analysis.error_clusterer import ErrorClusterer
from analysis.root_cause_analyzer import RootCauseAnalyzer
from analysis.timeline_builder import TimelineBuilder
from parsers.base_parser import LogEntry, LogLevel, LogSource


def _entry(
    i: int,
    ts: datetime | None,
    level: LogLevel,
    msg: str,
    rt: float | None = None,
) -> LogEntry:
    return LogEntry(
        raw_line=msg,
        timestamp=ts,
        level=level,
        source=LogSource.PYTHON,
        message=msg,
        line_number=i,
        response_time_ms=rt,
    )


def test_anomaly_detector_finds_error_spike():
    base = datetime(2024, 1, 15, 12, 0, 0)
    entries = []
    idx = 0
    for minute in range(5):
        ts0 = base + timedelta(minutes=minute)
        if minute == 2:
            for j in range(40):
                entries.append(
                    _entry(idx, ts0 + timedelta(seconds=j), LogLevel.ERROR, "err")
                )
                idx += 1
        else:
            for j in range(8):
                entries.append(
                    _entry(idx, ts0 + timedelta(seconds=j), LogLevel.INFO, "ok")
                )
                idx += 1
    with patch.object(config, "ANOMALY_ZSCORE_THRESHOLD", 1.5):
        d = AnomalyDetector()
        a = d.detect(entries)
        assert any(x.anomaly_type == "error_spike" for x in a)


def test_anomaly_detector_no_false_positive():
    base = datetime(2024, 1, 15, 12, 0, 0)
    entries = [
        _entry(i, base + timedelta(seconds=i), LogLevel.INFO, "ok")
        for i in range(40)
    ]
    d = AnomalyDetector()
    assert d.detect(entries) == []


def test_anomaly_detector_finds_silence():
    t0 = datetime(2024, 1, 15, 12, 0, 0)
    entries = []
    for i in range(20):
        entries.append(_entry(i, t0 + timedelta(seconds=i), LogLevel.INFO, "tick"))
    entries.append(
        _entry(20, t0 + timedelta(hours=1), LogLevel.INFO, "after long gap")
    )
    d = AnomalyDetector()
    assert any(x.anomaly_type == "silence" for x in d.detect(entries))


def test_error_clusterer_groups_similar(monkeypatch):
    class FakeModel:
        def encode(self, texts, show_progress_bar=False):
            n = len(texts)
            v = np.zeros((n, 8), dtype=np.float32)
            v[:, 0] = 1.0
            return v

    monkeypatch.setattr(ErrorClusterer, "_get_model", lambda self: FakeModel())

    entries = [
        LogEntry(
            raw_line="",
            timestamp=None,
            level=LogLevel.ERROR,
            source=LogSource.PYTHON,
            message="connection refused to localhost:5432",
            line_number=i,
        )
        for i in range(10)
    ]
    c = ErrorClusterer().cluster(entries)
    assert len(c) >= 1
    assert c[0].count >= 10


def test_error_clusterer_separates_distinct(monkeypatch):
    class FakeModel:
        def encode(self, texts, show_progress_bar=False):
            out = []
            for t in texts:
                if "OOM" in t:
                    out.append([1.0, 0.0])
                else:
                    out.append([0.0, 1.0])
            return np.array(out, dtype=np.float32)

    monkeypatch.setattr(ErrorClusterer, "_get_model", lambda self: FakeModel())

    entries = [
        LogEntry(
            raw_line="",
            timestamp=None,
            level=LogLevel.ERROR,
            source=LogSource.PYTHON,
            message="OOMKilled",
            line_number=1,
        ),
        LogEntry(
            raw_line="",
            timestamp=None,
            level=LogLevel.ERROR,
            source=LogSource.PYTHON,
            message="SSL certificate expired",
            line_number=2,
        ),
    ]
    c = ErrorClusterer().cluster(entries)
    assert len(c) >= 2


def test_root_cause_database():
    entries = [
        LogEntry(
            raw_line="",
            timestamp=None,
            level=LogLevel.ERROR,
            source=LogSource.PYTHON,
            message="connection refused to :5432",
            line_number=1,
        )
    ]
    r = RootCauseAnalyzer().analyze(entries, [], [])
    assert any(x.category == "database" for x in r)


def test_root_cause_memory():
    entries = [
        LogEntry(
            raw_line="",
            timestamp=None,
            level=LogLevel.ERROR,
            source=LogSource.PYTHON,
            message="OOMKilled container",
            line_number=1,
        )
    ]
    r = RootCauseAnalyzer().analyze(entries, [], [])
    assert any(x.category == "memory" for x in r)


def test_timeline_sorted():
    e1 = _entry(1, datetime(2024, 1, 1, 0, 0, 2), LogLevel.ERROR, "a")
    e2 = _entry(2, datetime(2024, 1, 1, 0, 0, 1), LogLevel.ERROR, "b")
    t = TimelineBuilder().build([e1, e2], [])
    times = [x.timestamp for x in t if x.timestamp]
    assert times == sorted(times)


def test_timeline_limits_events():
    with patch("analysis.timeline_builder.config.TIMELINE_MAX_EVENTS", 5):
        entries = [
            _entry(i, datetime(2024, 1, 1, 0, 0, 0) + timedelta(seconds=i), LogLevel.ERROR, f"e{i}")
            for i in range(1000)
        ]
        t = TimelineBuilder().build(entries, [])
        assert len(t) <= 5
