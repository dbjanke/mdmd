"""Structured logging: one `event=... key=value` line per event, to stderr.

Log entries carry event names, kinds, and counts, never document content, file
names, or settings values.
"""

import logging
import sys
from typing import Any

LOGGER_NAME = "mdmd"
_FIELDS_ATTR = "mdmd_fields"


class KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields: dict[str, Any] = getattr(record, _FIELDS_ATTR, {})
        parts = [
            f"ts={self.formatTime(record, '%Y-%m-%dT%H:%M:%S')}",
            f"level={record.levelname.lower()}",
            f"logger={record.name}",
            f"event={record.getMessage()}",
            *(f"{key}={_quote(value)}" for key, value in fields.items()),
        ]
        line = " ".join(parts)
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def _quote(value: object) -> str:
    text = str(value)
    if not text or any(ch.isspace() or ch in '"=' for ch in text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(KeyValueFormatter())
    root = logging.getLogger(LOGGER_NAME)
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: object) -> None:
    logger.log(level, event, extra={_FIELDS_ATTR: fields})
