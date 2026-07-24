"""systemd journal-style log parser."""

import re
from datetime import datetime
from parsers.base_parser import BaseParser, LogEntry, LogLevel, LogSource

# Jan 15 12:34:56 hostname service[1234]: message
_SYSTEMD = re.compile(
    r"^(\w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2}) (\S+) (\S+?)(?:\[(\d+)\])?: (.*)$"
)
# With priority: <0>message or journalctl -p
_PRI = re.compile(r"^<(\d)>(.*)$")


def _parse_syslog_time(s: str, year: int | None = None) -> datetime | None:
    y = year or datetime.now().year
    try:
        return datetime.strptime(f"{y} {s}", "%Y %b %d %H:%M:%S")
    except ValueError:
        return None


def _pri_to_level(pri: str) -> LogLevel:
    try:
        p = int(pri)
        if p <= 2:
            return LogLevel.CRITICAL
        if p <= 3:
            return LogLevel.ERROR
        if p <= 4:
            return LogLevel.WARNING
        if p <= 6:
            return LogLevel.INFO
        return LogLevel.DEBUG
    except ValueError:
        return LogLevel.UNKNOWN


class SystemdParser(BaseParser):
    def can_parse(self, sample_lines: list[str]) -> float:
        if not sample_lines:
            return 0.0
        hits = 0
        n = min(20, len(sample_lines))
        for line in sample_lines[:n]:
            s = line.strip()
            if _SYSTEMD.match(s) or (_PRI.match(s) and len(s) < 200):
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
            pm = _PRI.match(s)
            if pm:
                lvl = _pri_to_level(pm.group(1))
                msg = pm.group(2)
                entries.append(
                    LogEntry(
                        raw_line=line,
                        timestamp=None,
                        level=lvl,
                        source=LogSource.SYSTEMD,
                        message=msg,
                        line_number=i,
                    )
                )
                continue
            m = _SYSTEMD.match(s)
            if m:
                ts_s, host, unit, pid, msg = m.groups()
                ts = _parse_syslog_time(ts_s)
                level = _infer_level_from_message(msg)
                entries.append(
                    LogEntry(
                        raw_line=line,
                        timestamp=ts,
                        level=level,
                        source=LogSource.SYSTEMD,
                        message=msg,
                        host=host,
                        service=unit,
                        metadata={"pid": pid} if pid else {},
                        line_number=i,
                    )
                )
                continue
            self.last_skipped_lines += 1
        return entries


def _infer_level_from_message(msg: str) -> LogLevel:
    u = msg.upper()
    if "OOMKILL" in u or "OUT OF MEMORY" in u:
        return LogLevel.CRITICAL
    if "ERROR" in u or "FAILED" in u:
        return LogLevel.ERROR
    if "WARN" in u:
        return LogLevel.WARNING
    if "STARTED" in u or "STOPPING" in u:
        return LogLevel.INFO
    return LogLevel.INFO
