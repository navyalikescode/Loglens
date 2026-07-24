"""Kubernetes events and kubectl-style logs."""

import re
from datetime import datetime, timedelta
from parsers.base_parser import BaseParser, LogEntry, LogLevel, LogSource

# kubectl get events table row (flexible columns)
_EVENT_ROW = re.compile(
    r"^(\S+)\s+(Normal|Warning)\s+(\S+)\s+(\S+/[^\s]+)\s+(.+)$"
)
# Simpler: LAST SEEN TYPE REASON OBJECT MESSAGE (min 5 tokens after split)
_KUBECTL_LOG = re.compile(
    r"^(?P<pod>[\w.-]+)\s+(?P<container>[\w.-]+)\s+(?P<msg>.+)$"
)


def _age_to_dt(age: str) -> datetime | None:
    age = age.strip().lower()
    now = datetime.now()
    try:
        if age.endswith("s"):
            return now - timedelta(seconds=int(age[:-1]))
        if age.endswith("m"):
            return now - timedelta(minutes=int(age[:-1]))
        if age.endswith("h"):
            return now - timedelta(hours=int(age[:-1]))
        if age.endswith("d"):
            return now - timedelta(days=int(age[:-1]))
    except ValueError:
        pass
    return None


class K8sParser(BaseParser):
    def can_parse(self, sample_lines: list[str]) -> float:
        if not sample_lines:
            return 0.0
        hits = 0
        n = min(20, len(sample_lines))
        headerish = False
        for line in sample_lines[:n]:
            s = line.strip()
            if not s:
                continue
            if "LAST SEEN" in s and "REASON" in s:
                headerish = True
                hits += 1
            elif _EVENT_ROW.match(s):
                hits += 1
            elif "\t" in s and ("pod/" in s or "Pod" in s):
                hits += 1
        if headerish:
            return min(1.0, 0.5 + hits / max(1, n) * 0.5)
        if hits:
            return min(1.0, hits / max(1, n))
        return 0.0

    def parse(self, lines: list[str]) -> list[LogEntry]:
        self.last_skipped_lines = 0
        entries: list[LogEntry] = []
        skip_header = True
        for i, line in enumerate(lines, start=1):
            s = line.strip()
            if not s:
                continue
            if "LAST SEEN" in s and "TYPE" in s:
                skip_header = True
                continue
            m = _EVENT_ROW.match(s)
            if m:
                age_s, typ, reason, obj, msg = m.groups()
                ts = _age_to_dt(age_s)
                level = LogLevel.WARNING if typ == "Warning" else LogLevel.INFO
                entries.append(
                    LogEntry(
                        raw_line=line,
                        timestamp=ts,
                        level=level,
                        source=LogSource.KUBERNETES,
                        message=f"{reason}: {msg}",
                        service=obj,
                        metadata={"reason": reason, "type": typ},
                        line_number=i,
                    )
                )
                continue
            # kubectl logs: pod container message
            parts = s.split(None, 2)
            if len(parts) >= 3 and not s.startswith("/"):
                pod, container, msg = parts[0], parts[1], parts[2]
                if re.match(r"^[\w.-]+$", pod):
                    lvl = LogLevel.ERROR if "error" in msg.lower() else LogLevel.INFO
                    entries.append(
                        LogEntry(
                            raw_line=line,
                            timestamp=None,
                            level=lvl,
                            source=LogSource.KUBERNETES,
                            message=msg,
                            service=f"{pod}/{container}",
                            line_number=i,
                        )
                    )
                    continue
            self.last_skipped_lines += 1
        return entries
