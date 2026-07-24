"""Abstract base class for all log parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class LogSource(str, Enum):
    NGINX = "nginx"
    PYTHON = "python"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    SYSTEMD = "systemd"
    UNKNOWN = "unknown"


@dataclass
class LogEntry:
    raw_line: str
    timestamp: datetime | None
    level: LogLevel
    source: LogSource
    message: str
    service: str | None = None
    host: str | None = None
    request_id: str | None = None
    status_code: int | None = None
    response_time_ms: float | None = None
    stack_trace: str | None = None
    metadata: dict = field(default_factory=dict)
    line_number: int = 0


class BaseParser(ABC):
    def __init__(self) -> None:
        self.last_skipped_lines: int = 0

    @abstractmethod
    def can_parse(self, sample_lines: list[str]) -> float:
        """Return confidence 0.0-1.0 that this parser handles this log format."""

    @abstractmethod
    def parse(self, lines: list[str]) -> list[LogEntry]:
        """Parse lines into structured LogEntry objects."""

    def parse_text(self, text: str) -> list[LogEntry]:
        lines = text.strip().split("\n")
        return self.parse(lines)
