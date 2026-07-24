"""
Reconstructs a chronological timeline of significant events from log entries.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import config
from parsers.base_parser import LogLevel

if TYPE_CHECKING:
    from analysis.anomaly_detector import Anomaly
    from parsers.base_parser import LogEntry


@dataclass
class TimelineEvent:
    timestamp: datetime
    event_type: str
    description: str
    severity: str
    related_entries: list[int]


class TimelineBuilder:
    """
    Builds a timeline of significant events from entries and anomalies.
    """

    def build(
        self,
        entries: list["LogEntry"],
        anomalies: list["Anomaly"],
    ) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        seen_msg: set[str] = set()

        for e in entries:
            if e.level in (LogLevel.ERROR, LogLevel.CRITICAL):
                key = (e.message or "")[:120]
                if key not in seen_msg:
                    seen_msg.add(key)
                    events.append(
                        TimelineEvent(
                            timestamp=e.timestamp or datetime.min,
                            event_type="first_error",
                            description=(e.message or "")[:500],
                            severity="high"
                            if e.level == LogLevel.CRITICAL
                            else "medium",
                            related_entries=[e.line_number],
                        )
                    )
            if e.level == LogLevel.CRITICAL:
                events.append(
                    TimelineEvent(
                        timestamp=e.timestamp or datetime.min,
                        event_type="critical",
                        description=e.message[:500],
                        severity="critical",
                        related_entries=[e.line_number],
                    )
                )

            msg_l = (e.message or "").lower()
            if any(
                x in msg_l
                for x in (
                    "started",
                    "starting",
                    "container started",
                    "listening",
                )
            ):
                events.append(
                    TimelineEvent(
                        timestamp=e.timestamp or datetime.min,
                        event_type="service_restart",
                        description=e.message[:400],
                        severity="low",
                        related_entries=[e.line_number],
                    )
                )
            if "oomkilled" in msg_l or "out of memory" in msg_l:
                events.append(
                    TimelineEvent(
                        timestamp=e.timestamp or datetime.min,
                        event_type="resource",
                        description=e.message[:400],
                        severity="critical",
                        related_entries=[e.line_number],
                    )
                )

        for a in anomalies:
            events.append(
                TimelineEvent(
                    timestamp=a.timestamp,
                    event_type="anomaly",
                    description=a.description,
                    severity=a.severity,
                    related_entries=a.affected_lines[:50],
                )
            )

        # Recovery heuristic: INFO after ERROR window
        sorted_e = sorted(
            [e for e in entries if e.timestamp],
            key=lambda x: x.timestamp,
        )
        for i, e in enumerate(sorted_e):
            if e.level != LogLevel.INFO:
                continue
            prior = sorted_e[max(0, i - 5) : i]
            if any(
                p.level in (LogLevel.ERROR, LogLevel.CRITICAL) for p in prior
            ):
                events.append(
                    TimelineEvent(
                        timestamp=e.timestamp,
                        event_type="recovery",
                        description=f"Possible recovery: {e.message[:300]}",
                        severity="low",
                        related_entries=[e.line_number],
                    )
                )
                break

        max_e = config.TIMELINE_MAX_EVENTS
        events.sort(key=lambda ev: ev.timestamp or datetime.min)
        if len(events) > max_e:
            head = events[: max_e // 2]
            tail = events[-(max_e - len(head)) :]
            events = head + tail

        return events[:max_e]
