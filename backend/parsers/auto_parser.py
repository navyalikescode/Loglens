"""
Automatically detects log format and routes to the correct parser.
Tries each parser's can_parse() on the first 20 lines.
Uses the parser with the highest confidence score.
Falls back to a generic line-by-line parser if no parser scores above 0.3.
"""

import re
from datetime import datetime

import structlog

from parsers.base_parser import LogEntry, LogLevel, LogSource
from parsers.docker_parser import DockerParser
from parsers.k8s_parser import K8sParser
from parsers.nginx_parser import NginxParser
from parsers.python_parser import PythonParser
from parsers.systemd_parser import SystemdParser

logger = structlog.get_logger(__name__)

PARSERS = [NginxParser, PythonParser, DockerParser, K8sParser, SystemdParser]

_ISO_TS = re.compile(
    r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:[.,](\d+))?"
)
_SLASH_TS = re.compile(r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})")


def _extract_timestamp(line: str) -> datetime | None:
    m = _ISO_TS.search(line)
    if m:
        base = f"{m.group(1)} {m.group(2)}"
        for fmt in ("%Y-%m-%d %H:%M:%S",):
            try:
                return datetime.strptime(base, fmt)
            except ValueError:
                pass
    m2 = _SLASH_TS.search(line)
    if m2:
        try:
            return datetime.strptime(m2.group(1), "%Y/%m/%d %H:%M:%S")
        except ValueError:
            pass
    return None


def detect_and_parse(text: str) -> tuple[list[LogEntry], LogSource, int]:
    """
    Returns (parsed_entries, detected_source, skipped_lines).
    Tries all parsers on first 20 lines.
    Uses highest-confidence parser.
    If no parser confidence > 0.3, uses generic fallback.
    """
    lines = text.splitlines()
    if not lines:
        return [], LogSource.UNKNOWN, 0

    sample = lines[:20]
    best_cls: type | None = None
    best_score = 0.0
    for cls in PARSERS:
        p = cls()
        score = p.can_parse(sample)
        if score > best_score:
            best_score = score
            best_cls = cls

    if best_cls is None or best_score <= 0.3:
        logger.info(
            "auto_parser_fallback",
            best_score=best_score,
            reason="below_threshold",
        )
        entries = _generic_fallback_parse(lines)
        return entries, LogSource.UNKNOWN, 0

    parser = best_cls()
    entries = parser.parse(lines)
    skipped = getattr(parser, "last_skipped_lines", 0)
    if skipped:
        logger.debug("parser_skipped_lines", parser=best_cls.__name__, skipped=skipped)

    source_map = {
        NginxParser: LogSource.NGINX,
        PythonParser: LogSource.PYTHON,
        DockerParser: LogSource.DOCKER,
        K8sParser: LogSource.KUBERNETES,
        SystemdParser: LogSource.SYSTEMD,
    }
    return entries, source_map.get(best_cls, LogSource.UNKNOWN), skipped


def _generic_fallback_parse(lines: list[str]) -> list[LogEntry]:
    """
    Last resort parser. Tries to extract timestamps with common regex patterns.
    Detects level keywords (ERROR, WARN, INFO, DEBUG, CRITICAL) anywhere in line.
    Returns basic LogEntry for every line.
    """
    entries: list[LogEntry] = []
    level_kw = re.compile(
        r"\b(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\b", re.IGNORECASE
    )

    for i, line in enumerate(lines, start=1):
        s = line.rstrip("\n")
        if not s.strip():
            continue
        ts = _extract_timestamp(s)

        level = LogLevel.UNKNOWN
        lm = level_kw.search(s)
        if lm:
            level = _level_from_token(lm.group(1))

        entries.append(
            LogEntry(
                raw_line=line,
                timestamp=ts,
                level=level,
                source=LogSource.UNKNOWN,
                message=s.strip(),
                line_number=i,
            )
        )
    return entries


def _level_from_token(tok: str) -> LogLevel:
    t = tok.upper()
    if t == "WARN":
        return LogLevel.WARNING
    return getattr(LogLevel, t, LogLevel.UNKNOWN)
