"""Structured logging configuration.

Logs are emitted as human-readable lines in development and JSON in production.
A redaction filter prevents accidental logging of credentials and secrets.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

_SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "secret",
    "secret_key",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "external_id",
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
    "fernet_key",
}

_REDACTED = "***REDACTED***"


def _redact_value(value: Any, key: str | None = None) -> Any:
    if key and key.lower() in _SENSITIVE_KEYS:
        return _REDACTED
    if isinstance(value, dict):
        return {k: _redact_value(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(v, key) for v in value]
    if isinstance(value, str):
        # Redact obvious bearer tokens if they leak into free-form strings.
        return re.sub(r"(Bearer\s+)[A-Za-z0-9._\-]+", r"\1" + _REDACTED, value)
    return value


def _redaction_processor(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return _redact_value(event_dict)  # type: ignore[return-value]


def configure_logging(*, level: str = "INFO", json_logs: bool = False) -> None:
    """Configure stdlib logging and structlog."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
        force=True,
    )

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redaction_processor,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "cloudcostlens") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
