"""Shared logging configuration for spawn tools."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


_BASE_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__.keys())


class JsonFormatter(logging.Formatter):
    """Compact JSON formatter for non-interactive/systemd runs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _BASE_RECORD_FIELDS and not key.startswith("_")
        }
        if extras:
            payload["extra"] = extras
        return json.dumps(payload, sort_keys=True, default=str)


def _parse_level(value: str | None) -> int:
    if not value:
        return logging.INFO
    try:
        return int(value)
    except ValueError:
        return getattr(logging, value.upper(), logging.INFO)


def _choose_format(value: str | None, *, default: str) -> str:
    requested = (value or "").strip().lower()
    fmt = requested or default
    if fmt not in {"auto", "rich", "json", "plain"}:
        fmt = default
    return fmt


def configure_logging(
    *,
    app_name: str,
    default_format: str = "auto",
    force: bool = True,
) -> logging.Logger:
    """Configure root logging once for CLI/daemon runtime."""

    level = _parse_level(os.environ.get("SPAWN_LOG_LEVEL"))
    fmt = _choose_format(os.environ.get("SPAWN_LOG_FORMAT"), default=default_format)

    root = logging.getLogger()
    if force:
        root.handlers.clear()
    elif root.handlers:
        return logging.getLogger(app_name)
    root.setLevel(level)

    if fmt == "auto":
        fmt = "rich" if sys.stderr.isatty() else "json"

    handler: logging.Handler
    if fmt == "rich":
        try:
            from rich.console import Console
            from rich.logging import RichHandler

            handler = RichHandler(
                console=Console(stderr=True),
                rich_tracebacks=True,
                show_time=True,
                show_path=False,
                markup=False,
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
        except Exception:  # pragma: no cover
            handler = logging.StreamHandler(stream=sys.stderr)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    elif fmt == "plain":
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    else:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(JsonFormatter())

    handler.setLevel(level)
    root.addHandler(handler)
    logging.captureWarnings(True)
    return logging.getLogger(app_name)

