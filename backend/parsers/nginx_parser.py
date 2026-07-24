"""Nginx access and error log parser."""

import re
from datetime import datetime, timezone
import structlog

from parsers.base_parser import BaseParser, LogEntry, LogLevel, LogSource

logger = structlog.get_logger(__name__)

# Combined-style access log (referrer and UA optional)
_ACCESS_COMBINED = re.compile(
    r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) ([^"]+)" (\d{3}) (\S+)'
    r'(?: "([^"]*)" "([^"]*)")?'
    r'(?: rt=([\d.]+))?$'  # optional request_time suffix some configs add
)

# Nginx error log
_ERROR = re.compile(
    r"^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) \[(?P<lvl>\w+)\] (?P<msg>.+)$"
)


def _parse_nginx_time(s: str) -> datetime | None:
    """Parse Nginx access log time: 10/Oct/2000:13:55:36 -0700"""
    try:
        ts = datetime.strptime(s, "%d/%b/%Y:%H:%M:%S %z")
        # Normalize to naive UTC so access/error entries are comparable.
        return ts.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.strptime(s, "%d/%b/%Y:%H:%M:%S")
        except ValueError:
            return None


def _parse_error_time(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y/%m/%d %H:%M:%S")
    except ValueError:
        return None


class NginxParser(BaseParser):
    def can_parse(self, sample_lines: list[str]) -> float:
        if not sample_lines:
            return 0.0
        access_hits = 0
        error_hits = 0
        n = min(len(sample_lines), 20)
        for line in sample_lines[:n]:
            s = line.strip()
            if not s:
                continue
            if _ACCESS_COMBINED.match(s):
                access_hits += 1
            elif _ERROR.match(s):
                error_hits += 1
        total = access_hits + error_hits
        if total == 0:
            return 0.0
        return min(1.0, total / max(1, n) * 1.2)

    def parse(self, lines: list[str]) -> list[LogEntry]:
        self.last_skipped_lines = 0
        entries: list[LogEntry] = []
        for i, line in enumerate(lines, start=1):
            s = line.strip()
            if not s:
                continue
            m = _ACCESS_COMBINED.match(s)
            if m:
                ts_raw, status_s = m.group(2), m.group(6)
                status = int(status_s)
                if status >= 500:
                    level = LogLevel.ERROR
                elif status >= 400:
                    level = LogLevel.WARNING
                else:
                    level = LogLevel.INFO
                rt_ms = None
                if m.group(9):
                    try:
                        rt_ms = float(m.group(9)) * 1000.0
                    except ValueError:
                        pass
                msg = f"{m.group(3)} {m.group(4)} {status_s}"
                entries.append(
                    LogEntry(
                        raw_line=line,
                        timestamp=_parse_nginx_time(ts_raw),
                        level=level,
                        source=LogSource.NGINX,
                        message=msg,
                        status_code=status,
                        response_time_ms=rt_ms,
                        line_number=i,
                        metadata={"path": m.group(4)},
                    )
                )
                continue
            em = _ERROR.match(s)
            if em:
                ts_raw = em.group(1)
                lvl = em.group("lvl").lower()
                if lvl == "error" or lvl == "crit":
                    level = LogLevel.ERROR
                elif lvl == "warn":
                    level = LogLevel.WARNING
                else:
                    level = LogLevel.INFO
                entries.append(
                    LogEntry(
                        raw_line=line,
                        timestamp=_parse_error_time(ts_raw),
                        level=level,
                        source=LogSource.NGINX,
                        message=em.group("msg"),
                        line_number=i,
                    )
                )
                continue
            self.last_skipped_lines += 1
        if self.last_skipped_lines:
            logger.info(
                "nginx_parse_skipped",
                skipped_malformed=self.last_skipped_lines,
            )
        return entries
