"""
Detects anomalies in log streams using statistical methods.
Fast enough to run on 50k lines in under 5 seconds on CPU.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
from scipy import stats

import config
from parsers.base_parser import LogLevel

if TYPE_CHECKING:
    from parsers.base_parser import LogEntry


@dataclass
class Anomaly:
    timestamp: datetime
    anomaly_type: str  # "error_spike", "latency_spike", "silence", "cascade_failure"
    severity: str  # "low", "medium", "high", "critical"
    description: str
    affected_lines: list[int]
    z_score: float
    baseline_value: float
    observed_value: float


class AnomalyDetector:
    """
    Detects four types of anomalies:

    1. ERROR SPIKE — z-score on error rate per time window exceeds threshold
    2. LATENCY SPIKE — z-score on response times
    3. SILENCE — gap in log output significantly longer than baseline
    4. CASCADE FAILURE — error rate stays elevated for 3+ consecutive windows
    """

    def __init__(self) -> None:
        self._threshold = config.ANOMALY_ZSCORE_THRESHOLD

    def detect(self, entries: list["LogEntry"]) -> list[Anomaly]:
        anomalies: list[Anomaly] = []
        anomalies.extend(self._detect_error_spikes(entries))
        anomalies.extend(self._detect_latency_spikes(entries))
        anomalies.extend(self._detect_silence(entries))
        anomalies.extend(self._detect_cascade_failure(entries))
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        def sort_key(a: Anomaly) -> tuple[int, datetime]:
            return (sev_order.get(a.severity, 3), a.timestamp or datetime.min)

        return sorted(anomalies, key=sort_key)

    def _window_key(self, ts: datetime) -> datetime:
        return ts.replace(second=0, microsecond=0)

    def _detect_error_spikes(self, entries: list["LogEntry"]) -> list[Anomaly]:
        out: list[Anomaly] = []
        with_ts = [e for e in entries if e.timestamp]
        if len(with_ts) < 5:
            return out

        by_window: dict[datetime, list] = defaultdict(list)
        for e in with_ts:
            by_window[self._window_key(e.timestamp)].append(e)

        windows = sorted(by_window.keys())
        rates: list[float] = []
        window_lines: list[list[int]] = []
        for w in windows:
            bucket = by_window[w]
            errs = sum(
                1
                for e in bucket
                if e.level in (LogLevel.ERROR, LogLevel.CRITICAL)
            )
            total = len(bucket)
            rates.append(errs / max(total, 1))
            window_lines.append([e.line_number for e in bucket])

        if len(rates) < 3:
            return out

        arr = np.array(rates, dtype=float)
        z = np.abs(stats.zscore(arr))
        mean_r = float(np.mean(arr))
        for i, w in enumerate(windows):
            if z[i] > self._threshold and rates[i] > mean_r and rates[i] > 0:
                sev = "high" if rates[i] > 0.5 else "medium"
                out.append(
                    Anomaly(
                        timestamp=w,
                        anomaly_type="error_spike",
                        severity=sev,
                        description=(
                            f"Error rate spike in 1m window: {rates[i]:.1%} "
                            f"(z={z[i]:.2f})"
                        ),
                        affected_lines=window_lines[i][:200],
                        z_score=float(z[i]),
                        baseline_value=mean_r,
                        observed_value=rates[i],
                    )
                )
        return out

    def _detect_latency_spikes(self, entries: list["LogEntry"]) -> list[Anomaly]:
        out: list[Anomaly] = []
        lat = [
            (e, e.response_time_ms)
            for e in entries
            if e.response_time_ms is not None and e.response_time_ms > 0
        ]
        if len(lat) < 10:
            return out
        values = np.array([x[1] for x in lat], dtype=float)
        mu = float(np.mean(values))
        sigma = float(np.std(values)) or 1e-6
        z = (values - mu) / sigma
        for (e, v), zi in zip(lat, z):
            if zi > self._threshold:
                out.append(
                    Anomaly(
                        timestamp=e.timestamp or datetime.min,
                        anomaly_type="latency_spike",
                        severity="medium",
                        description=(
                            f"High response time {v:.1f}ms "
                            f"(z={zi:.2f} vs baseline {mu:.1f}ms)"
                        ),
                        affected_lines=[e.line_number],
                        z_score=float(zi),
                        baseline_value=mu,
                        observed_value=float(v),
                    )
                )
        return out

    def _detect_silence(self, entries: list["LogEntry"]) -> list[Anomaly]:
        out: list[Anomaly] = []
        with_ts = [e for e in entries if e.timestamp]
        if len(with_ts) < 5:
            return out
        with_ts.sort(key=lambda e: e.timestamp)
        gap_secs: list[float] = []
        gap_meta: list[tuple[int, int, datetime]] = []
        for a, b in zip(with_ts, with_ts[1:]):
            dt = b.timestamp - a.timestamp
            s = dt.total_seconds()
            if s > 0:
                gap_secs.append(s)
                gap_meta.append((a.line_number, b.line_number, b.timestamp))

        if len(gap_secs) < 3:
            return out

        secs = np.array(gap_secs, dtype=float)
        mu = float(np.mean(secs))
        sigma = float(np.std(secs)) or 1e-6
        threshold = mu + 3 * sigma
        for s, (la, lb, ts_end) in zip(secs, gap_meta):
            if s > threshold and s > 60:
                z = (s - mu) / sigma
                out.append(
                    Anomaly(
                        timestamp=ts_end,
                        anomaly_type="silence",
                        severity="high" if s > mu + 5 * sigma else "medium",
                        description=(
                            f"Log silence gap {s:.0f}s "
                            f"(baseline ~{mu:.0f}s, threshold {threshold:.0f}s)"
                        ),
                        affected_lines=[la, lb],
                        z_score=float(z),
                        baseline_value=mu,
                        observed_value=float(s),
                    )
                )
        return out

    def _detect_cascade_failure(self, entries: list["LogEntry"]) -> list[Anomaly]:
        out: list[Anomaly] = []
        with_ts = [e for e in entries if e.timestamp]
        if len(with_ts) < 10:
            return out

        by_window: dict[datetime, list] = defaultdict(list)
        for e in with_ts:
            by_window[self._window_key(e.timestamp)].append(e)

        windows = sorted(by_window.keys())
        if len(windows) < 4:
            return out

        flags: list[bool] = []
        window_err_lines: list[list[int]] = []
        mean_r = 0.0
        rates: list[float] = []
        for w in windows:
            bucket = by_window[w]
            errs = sum(
                1
                for e in bucket
                if e.level in (LogLevel.ERROR, LogLevel.CRITICAL)
            )
            r = errs / max(len(bucket), 1)
            rates.append(r)
            window_err_lines.append(
                [e.line_number for e in bucket if e.level in (LogLevel.ERROR, LogLevel.CRITICAL)]
            )

        mean_r = float(np.mean(rates)) or 1e-6
        arr = np.array(rates, dtype=float)
        z = np.abs(stats.zscore(arr))

        for i in range(len(windows)):
            flags.append(z[i] > self._threshold and rates[i] > mean_r * 1.5)

        run_start = None
        for i, f in enumerate(flags):
            if f and run_start is None:
                run_start = i
            elif not f and run_start is not None:
                if i - run_start >= 3:
                    affected: list[int] = []
                    for j in range(run_start, i):
                        affected.extend(window_err_lines[j][:50])
                    out.append(
                        Anomaly(
                            timestamp=windows[run_start],
                            anomaly_type="cascade_failure",
                            severity="critical",
                            description=(
                                f"Sustained elevated errors for {i - run_start} "
                                "consecutive minute windows"
                            ),
                            affected_lines=affected[:300],
                            z_score=float(np.max(z[run_start:i])),
                            baseline_value=mean_r,
                            observed_value=float(np.mean(rates[run_start:i])),
                        )
                    )
                run_start = None
        if run_start is not None and len(flags) - run_start >= 3:
            i = len(flags)
            affected = []
            for j in range(run_start, i):
                affected.extend(window_err_lines[j][:50])
            out.append(
                Anomaly(
                    timestamp=windows[run_start],
                    anomaly_type="cascade_failure",
                    severity="critical",
                    description=(
                        f"Sustained elevated errors for {i - run_start} "
                        "consecutive minute windows"
                    ),
                    affected_lines=affected[:300],
                    z_score=float(np.max(z[run_start:i])),
                    baseline_value=mean_r,
                    observed_value=float(np.mean(rates[run_start:i])),
                )
            )
        return out
