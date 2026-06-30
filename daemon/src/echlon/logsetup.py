"""Structured logging for the daemon.

A long-running daemon needs to be diagnosable after the fact: who started which
session, what failed, how long it ran. We emit one JSON object per line to
stderr (greppable, machine-parseable, plays well with `jq` and log shippers) and
keep human `print`s only for the CLI's interactive UX.

Modules log via ``logging.getLogger(__name__)`` (already under the ``echlon.*``
namespace); ``setup_logging()`` configures that namespace once. Pass structured
fields with ``extra=``, e.g. ``log.info("session start", extra={"session": sid})``.

Env:
  ECHLON_LOG_LEVEL   DEBUG | INFO | WARNING | ERROR   (default INFO)
  ECHLON_LOG_FORMAT  json | plain                     (default json)
"""

from __future__ import annotations

import json
import logging
import os
import sys

_ROOT = "echlon"
_configured = False

# LogRecord attributes that are built-in; anything else is a caller-supplied
# `extra=` field we want to surface in the structured payload.
_STD_ATTRS = frozenset(
    logging.makeLogRecord({}).__dict__
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """Render a LogRecord as a single JSON line, including any `extra` fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str | None = None, fmt: str | None = None) -> logging.Logger:
    """Configure the ``echlon`` logger namespace. Idempotent.

    Returns the configured root ``echlon`` logger.
    """
    global _configured
    root = logging.getLogger(_ROOT)
    if _configured:
        return root

    level = (level or os.getenv("ECHLON_LOG_LEVEL") or "INFO").upper()
    fmt = (fmt or os.getenv("ECHLON_LOG_FORMAT") or "json").lower()

    handler = logging.StreamHandler(sys.stderr)
    if fmt == "plain":
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    else:
        handler.setFormatter(JsonFormatter())

    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level, logging.INFO))
    root.propagate = False  # don't double-log through the python root logger
    _configured = True
    return root


def get_logger(name: str) -> logging.Logger:
    """Logger for a submodule, e.g. get_logger(__name__)."""
    return logging.getLogger(name)
