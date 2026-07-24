"""Python / FastAPI / uvicorn log parser with traceback merging."""

import re
from datetime import datetime
from parsers.base_parser import BaseParser, LogEntry, LogLevel, LogSource

_STD_LOGGING = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (\w+) ([^:]+:[^\s]+|\S+) (.*)$"
)
_STD_LOGGING2 = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) ([^:]+):(\d+) (.*)$"
)
_UVICORN = re.compile(
    r"^(INFO|WARNING|ERROR|DEBUG|CRITICAL):\s+([\d.]+:\d+)\s+-\s+"
    r'"([^"]+)"\s+(\d+)'
)
_TRACE_START = re.compile(r"^Traceback \(most recent call last\):")


def _level_from_str(s: str) -> LogLevel:
    m = {
        "DEBUG": LogLevel.DEBUG,
        "INFO": LogLevel.INFO,
        "WARNING": LogLevel.WARNING,
        "WARN": LogLevel.WARNING,
        "ERROR": LogLevel.ERROR,
        "CRITICAL": LogLevel.CRITICAL,
    }
    return m.get(s.upper(), LogLevel.UNKNOWN)


def _parse_ts(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


class PythonParser(BaseParser):
    def can_parse(self, sample_lines: list[str]) -> float:
        if not sample_lines:
            return 0.0
        hits = 0
        n = min(20, len(sample_lines))
        for line in sample_lines[:n]:
            s = line.strip()
            if not s:
                continue
            if _TRACE_START.match(s):
                hits += 3
                continue
            if (
                _STD_LOGGING.match(s)
                or _STD_LOGGING2.match(s)
                or _UVICORN.match(s)
                or " - ERROR - " in s
                or s.startswith("INFO:     ")
            ):
                hits += 1
        if hits == 0:
            return 0.0
        return min(1.0, hits / max(1, n) * 1.1)

    def parse(self, lines: list[str]) -> list[LogEntry]:
        self.last_skipped_lines = 0
        entries: list[LogEntry] = []
        i = 0
        line_no = 0
        while i < len(lines):
            raw = lines[i]
            line_no = i + 1
            s = raw.rstrip()
            if not s.strip():
                i += 1
                continue

            if _TRACE_START.match(s.strip()):
                start = i
                block = [s]
                i += 1
                while i < len(lines):
                    nxt = lines[i]
                    if not nxt.strip():
                        block.append(nxt)
                        i += 1
                        continue
                    # Continuation: indented or exception final line
                    stripped = nxt.lstrip()
                    if nxt.startswith(" ") or nxt.startswith("\t"):
                        block.append(nxt.rstrip("\n"))
                        i += 1
                        continue
                    if re.match(r"^[\w.]+: .+", stripped):
                        block.append(nxt.rstrip("\n"))
                        i += 1
                        break
                    break
                full = "\n".join(block)
                entries.append(
                    LogEntry(
                        raw_line=raw,
                        timestamp=None,
                        level=LogLevel.ERROR,
                        source=LogSource.PYTHON,
                        message=block[-1][:500] if block else "Traceback",
                        stack_trace=full,
                        line_number=start + 1,
                    )
                )
                continue

            m = _STD_LOGGING.match(s)
            if m:
                ts, lvl, _loc, msg = m.groups()
                entries.append(
                    LogEntry(
                        raw_line=raw,
                        timestamp=_parse_ts(ts),
                        level=_level_from_str(lvl),
                        source=LogSource.PYTHON,
                        message=msg,
                        line_number=line_no,
                    )
                )
                i += 1
                continue

            m2 = _STD_LOGGING2.match(s)
            if m2:
                ts, lvl, mod, _ln, msg = m2.groups()
                entries.append(
                    LogEntry(
                        raw_line=raw,
                        timestamp=_parse_ts(ts),
                        level=_level_from_str(lvl),
                        source=LogSource.PYTHON,
                        message=msg,
                        service=mod,
                        line_number=line_no,
                    )
                )
                i += 1
                continue

            um = _UVICORN.match(s)
            if um:
                lvl_s, _addr, request_line, status_s = um.groups()
                status = int(status_s)
                if status >= 500:
                    level = LogLevel.ERROR
                elif status >= 400:
                    level = LogLevel.WARNING
                else:
                    level = LogLevel.INFO
                entries.append(
                    LogEntry(
                        raw_line=raw,
                        timestamp=None,
                        level=level,
                        source=LogSource.PYTHON,
                        message=f'"{request_line}" {status_s}',
                        status_code=status,
                        line_number=line_no,
                    )
                )
                i += 1
                continue

            if s.startswith("INFO:     ") or s.startswith("ERROR:    "):
                lvl = LogLevel.ERROR if "ERROR" in s[:20] else LogLevel.INFO
                entries.append(
                    LogEntry(
                        raw_line=raw,
                        timestamp=None,
                        level=lvl,
                        source=LogSource.PYTHON,
                        message=s,
                        line_number=line_no,
                    )
                )
                i += 1
                continue

            entries.append(
                LogEntry(
                    raw_line=raw,
                    timestamp=None,
                    level=LogLevel.INFO,
                    source=LogSource.PYTHON,
                    message=s,
                    line_number=line_no,
                )
            )
            i += 1

        return entries
