"""
Identifies the most likely root cause using rules and heuristics.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from analysis.anomaly_detector import Anomaly
    from analysis.error_clusterer import ErrorCluster
    from parsers.base_parser import LogEntry


@dataclass
class RootCause:
    hypothesis: str
    confidence: str
    evidence: list[str]
    category: str
    first_signal_at: datetime | None
    recommended_actions: list[str]


class RootCauseAnalyzer:
    """
    Rule-based root cause detection. First matching strong signal wins per rule;
    multiple hypotheses returned when several rules match with evidence.
    """

    def analyze(
        self,
        entries: list["LogEntry"],
        anomalies: list["Anomaly"],
        clusters: list["ErrorCluster"],
    ) -> list[RootCause]:
        text_blob = "\n".join(
            (e.message or "") + "\n" + (e.stack_trace or "")
            for e in entries
        ).lower()
        hypotheses: list[RootCause] = []

        def earliest_matching(pred) -> datetime | None:
            ts_list = [e.timestamp for e in entries if e.timestamp and pred(e)]
            return min(ts_list) if ts_list else None

        # RULE 1 — Database
        port_hit = bool(re.search(r":(5432|3306|27017)\b", text_blob))
        db_flags = [
            "connection refused" in text_blob and port_hit,
            "too many connections" in text_blob,
            "password authentication failed" in text_blob,
            "sqlalchemy" in text_blob and "operationalerror" in text_blob,
            "could not connect to server" in text_blob,
        ]
        if any(db_flags):
            labels = [
                "connection refused to DB port",
                "too many connections",
                "password authentication failed",
                "SQLAlchemy operational error",
                "could not connect to server",
            ]
            ev = [labels[i] for i, ok in enumerate(db_flags) if ok]
            hypotheses.append(
                RootCause(
                    hypothesis="Database connectivity or authentication failure likely caused the outage.",
                    confidence="high" if len(ev) >= 2 else "medium",
                    evidence=ev,
                    category="database",
                    first_signal_at=earliest_matching(
                        lambda e: "connection" in (e.message or "").lower()
                    ),
                    recommended_actions=[
                        "Verify database availability and credentials.",
                        "Check connection pool sizing and idle timeouts.",
                        "Review DB logs for refused connections or auth errors.",
                    ],
                )
            )

        # RULE 2 — Memory
        mem_pat = re.compile(
            r"memoryerror|oomkilled|cannot allocate memory|out of memory",
            re.I,
        )
        if mem_pat.search(text_blob) or (
            "killed" in text_blob and "oom" in text_blob
        ):
            hypotheses.append(
                RootCause(
                    hypothesis="Memory exhaustion or OOM kill likely involved.",
                    confidence="high",
                    evidence=[m.group(0) for m in mem_pat.finditer(text_blob)][:3]
                    or ["OOM-related signals in logs"],
                    category="memory",
                    first_signal_at=earliest_matching(
                        lambda e: bool(mem_pat.search(e.message or ""))
                    ),
                    recommended_actions=[
                        "Inspect container/pod memory limits and host memory pressure.",
                        "Profile application memory usage and leaks.",
                        "Scale or increase memory limits if legitimate growth.",
                    ],
                )
            )

        # RULE 3 — Dependency / upstream
        dep = False
        ev_dep: list[str] = []
        if re.search(r"\b502\b|\b503\b|\b504\b", text_blob):
            dep = True
            ev_dep.append("Multiple 502/503/504 responses observed")
        if "upstream timed out" in text_blob or "bad gateway" in text_blob:
            dep = True
            ev_dep.append("Upstream timeout / bad gateway messages")
        if "health check" in text_blob and "fail" in text_blob:
            dep = True
            ev_dep.append("Health check failures")
        if dep:
            hypotheses.append(
                RootCause(
                    hypothesis="Downstream or upstream dependency failure caused user-facing errors.",
                    confidence="high" if len(ev_dep) >= 2 else "medium",
                    evidence=ev_dep,
                    category="dependency",
                    first_signal_at=earliest_matching(
                        lambda e: bool(
                            re.search(r"502|503|504", e.message or "")
                        )
                    ),
                    recommended_actions=[
                        "Check upstream services and load balancer configuration.",
                        "Validate network paths between tiers.",
                        "Review retry and timeout settings.",
                    ],
                )
            )

        # RULE 4 — Resource exhaustion (disk / fds)
        res_pat = re.compile(
            r"no space left on device|too many open files|resource temporarily unavailable",
            re.I,
        )
        if res_pat.search(text_blob):
            hypotheses.append(
                RootCause(
                    hypothesis="Disk or file descriptor exhaustion detected.",
                    confidence="high",
                    evidence=[m.group(0) for m in res_pat.finditer(text_blob)][:3],
                    category="resource_exhaustion",
                    first_signal_at=earliest_matching(
                        lambda e: bool(res_pat.search(e.message or ""))
                    ),
                    recommended_actions=[
                        "Free disk space or expand volumes.",
                        "Raise ulimits / review file handle leaks.",
                        "Rotate logs and audit large writes.",
                    ],
                )
            )

        # RULE 5 — Configuration
        cfg_pat = re.compile(
            r"invalid configuration|environment variable not set|filenotfounderror.*\.(ya?ml|json|env)",
            re.I,
        )
        if cfg_pat.search(text_blob) or "configuration error" in text_blob:
            hypotheses.append(
                RootCause(
                    hypothesis="Misconfiguration or missing configuration caused startup/runtime failure.",
                    confidence="medium",
                    evidence=["Configuration-related errors in logs"],
                    category="configuration",
                    first_signal_at=earliest_matching(
                        lambda e: bool(cfg_pat.search(e.message or ""))
                    ),
                    recommended_actions=[
                        "Validate environment variables and mounted config files.",
                        "Compare with known-good configuration templates.",
                        "Add schema validation for config at startup.",
                    ],
                )
            )

        # RULE 6 — Code error
        if any(e.stack_trace for e in entries) or re.search(
            r"traceback|unhandled exception|assertionerror", text_blob
        ):
            hypotheses.append(
                RootCause(
                    hypothesis="Unhandled application exception indicates a code defect or unexpected input.",
                    confidence="high" if any(e.stack_trace for e in entries) else "medium",
                    evidence=["Python tracebacks or exception strings present"],
                    category="code_error",
                    first_signal_at=earliest_matching(lambda e: bool(e.stack_trace)),
                    recommended_actions=[
                        "Triage stack trace to failing module.",
                        "Add guards and tests around failing path.",
                        "Deploy hotfix after root fix is verified.",
                    ],
                )
            )

        # RULE 7 — Network
        net_pat = re.compile(
            r"dns resolution failed|ssl certificate|certificate expired|tls handshake|connection reset by peer",
            re.I,
        )
        if net_pat.search(text_blob):
            hypotheses.append(
                RootCause(
                    hypothesis="Network, DNS, or TLS issues detected.",
                    confidence="medium",
                    evidence=[m.group(0) for m in net_pat.finditer(text_blob)][:3],
                    category="network",
                    first_signal_at=earliest_matching(
                        lambda e: bool(net_pat.search(e.message or ""))
                    ),
                    recommended_actions=[
                        "Verify DNS records and resolver health.",
                        "Check TLS certificate validity and chain.",
                        "Inspect firewall and security group rules.",
                    ],
                )
            )

        if not hypotheses:
            hypotheses.append(
                RootCause(
                    hypothesis="No strong automated rule matched; manual investigation required.",
                    confidence="low",
                    evidence=["Insufficient distinctive signals in parsed logs"],
                    category="dependency",
                    first_signal_at=None,
                    recommended_actions=[
                        "Correlate with deployments and infra changes.",
                        "Narrow time window around first customer impact.",
                        "Collect metrics alongside logs for context.",
                    ],
                )
            )

        conf_order = {"high": 0, "medium": 1, "low": 2}
        hypotheses.sort(
            key=lambda h: (
                conf_order.get(h.confidence, 2),
                h.first_signal_at or datetime.max,
            )
        )
        return hypotheses
