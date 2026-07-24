"""Docker container log parser."""

import re
from datetime import datetime, timezone
from parsers.base_parser import BaseParser, LogEntry, LogLevel, LogSource

# RFC3339 nano + stream + F + message (Kubernetes/docker json-driver style)
_DOCKER_RFC = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z) (stdout|stderr) F (.*)$"
)
# container_name | timestamp LEVEL message
_PIPE = re.compile(
    r"^([^|]+)\s*\|\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$"
)


def _parse_rfc3339(s: str) -> datetime | None:
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except ValueError:
        return None


class DockerParser(BaseParser):
    def can_parse(self, sample_lines: list[str]) -> float:
        if not sample_lines:
            return 0.0
        hits = 0
        n = min(20, len(sample_lines))
        for line in sample_lines[:n]:
            s = line.strip()
            if _DOCKER_RFC.match(s) or _PIPE.match(s) or " stdout " in s or " stderr " in s:
                hits += 1
        if hits == 0:
            return 0.0
        return min(1.0, hits / max(1, n))

    def parse(self, lines: list[str]) -> list[LogEntry]:
        self.last_skipped_lines = 0
        entries: list[LogEntry] = []
        for i, line in enumerate(lines, start=1):
            s = line.strip()
            if not s:
                continue
            m = _DOCKER_RFC.match(s)
            if m:
                ts_s, stream, msg = m.groups()
                ts = _parse_rfc3339(ts_s)
                if ts and ts.tzinfo:
                    ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
                level = LogLevel.WARNING if stream == "stderr" else LogLevel.INFO
                entries.append(
                    LogEntry(
                        raw_line=line,
                        timestamp=ts,
                        level=level,
                        source=LogSource.DOCKER,
                        message=msg,
                        metadata={"stream": stream},
                        line_number=i,
                    )
                )
                continue
            pm = _PIPE.match(s)
            if pm:
                name, ts_s, lvl, msg = pm.groups()
                try:
                    ts = datetime.strptime(ts_s, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    ts = None
                entries.append(
                    LogEntry(
                        raw_line=line,
                        timestamp=ts,
                        level=_docker_level(lvl),
                        source=LogSource.DOCKER,
                        message=msg,
                        service=name.strip(),
                        line_number=i,
                    )
                )
                continue
            entries.append(
                LogEntry(
                    raw_line=line,
                    timestamp=None,
                    level=LogLevel.INFO,
                    source=LogSource.DOCKER,
                    message=s,
                    line_number=i,
                )
            )
        return entries


def _docker_level(lvl: str) -> LogLevel:
    return {
        "ERROR": LogLevel.ERROR,
        "WARN": LogLevel.WARNING,
        "WARNING": LogLevel.WARNING,
        "INFO": LogLevel.INFO,
        "DEBUG": LogLevel.DEBUG,
    }.get(lvl.upper(), LogLevel.INFO)
