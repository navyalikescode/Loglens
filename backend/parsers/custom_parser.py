"""
User-defined custom log parser.
Users provide a regex pattern with named groups to parse their custom log formats.
Required named groups: 'message'
Optional named groups: 'timestamp', 'level', 'service', 'host'
"""

import re
from datetime import datetime

import structlog

from parsers.base_parser import BaseParser, LogEntry, LogLevel, LogSource

logger = structlog.get_logger(__name__)

TIMESTAMP_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d/%b/%Y:%H:%M:%S",
    "%b %d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%f",
]

LEVEL_MAP = {
    "debug": LogLevel.DEBUG,
    "info": LogLevel.INFO,
    "warn": LogLevel.WARNING,
    "warning": LogLevel.WARNING,
    "error": LogLevel.ERROR,
    "err": LogLevel.ERROR,
    "critical": LogLevel.CRITICAL,
    "fatal": LogLevel.CRITICAL,
    "crit": LogLevel.CRITICAL,
}


def _parse_ts(raw: str) -> datetime | None:
    raw = raw.strip()
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _parse_level(raw: str) -> LogLevel:
    return LEVEL_MAP.get(raw.strip().lower(), LogLevel.UNKNOWN)


class CustomParser(BaseParser):
    def __init__(self, pattern: str):
        super().__init__()
        self.regex = re.compile(pattern)
        self.group_names = set(self.regex.groupindex.keys())

    def can_parse(self, sample_lines: list[str]) -> float:
        if not sample_lines:
            return 0.0
        matched = sum(1 for line in sample_lines if self.regex.search(line))
        return matched / len(sample_lines)

    def parse(self, lines: list[str]) -> list[LogEntry]:
        entries = []
        skipped = 0
        for i, line in enumerate(lines, start=1):
            raw = line.rstrip("\n")
            if not raw.strip():
                continue
            m = self.regex.search(raw)
            if not m:
                skipped += 1
                entries.append(LogEntry(
                    raw_line=line, timestamp=None, level=LogLevel.UNKNOWN,
                    source=LogSource.UNKNOWN, message=raw.strip(), line_number=i,
                ))
                continue

            groups = m.groupdict()
            ts = _parse_ts(groups["timestamp"]) if "timestamp" in groups else None
            level = _parse_level(groups["level"]) if "level" in groups else LogLevel.UNKNOWN
            message = groups.get("message", raw.strip())
            service = groups.get("service")
            host = groups.get("host")

            entries.append(LogEntry(
                raw_line=line, timestamp=ts, level=level,
                source=LogSource.UNKNOWN, message=message,
                service=service, host=host, line_number=i,
            ))

        self.last_skipped_lines = skipped
        return entries


_custom_formats: dict[str, dict] = {}


def register_custom_format(name: str, pattern: str, description: str = "") -> dict:
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex: {e}")

    named_groups = set(re.compile(pattern).groupindex.keys())
    if "message" not in named_groups:
        raise ValueError("Pattern must include a 'message' named group, e.g. (?P<message>...)")

    _custom_formats[name] = {
        "name": name,
        "pattern": pattern,
        "description": description,
        "groups": sorted(named_groups),
    }
    logger.info("custom_format_registered", name=name, groups=sorted(named_groups))
    return _custom_formats[name]


def get_custom_formats() -> list[dict]:
    return list(_custom_formats.values())


def get_custom_parser(name: str) -> CustomParser | None:
    fmt = _custom_formats.get(name)
    if not fmt:
        return None
    return CustomParser(fmt["pattern"])


def remove_custom_format(name: str) -> bool:
    return _custom_formats.pop(name, None) is not None
