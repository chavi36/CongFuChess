"""Structured logging with correlation IDs for Kung-Fu Chess services."""

import json
import logging
import time
import uuid
from typing import Any


def _emit(level: str, msg: str, **fields: Any) -> None:
    record = {
        "ts": time.time(),
        "level": level,
        "msg": msg,
        **fields,
    }
    print(json.dumps(record), flush=True)


def info(msg: str, **fields: Any) -> None:
    _emit("info", msg, **fields)


def error(msg: str, **fields: Any) -> None:
    _emit("error", msg, **fields)


def new_correlation_id() -> str:
    return str(uuid.uuid4())


class RequestLogger:
    """Attach a correlation_id to every log call for a request/command lifetime."""

    def __init__(self, correlation_id: str | None = None, **base_fields: Any) -> None:
        self.correlation_id = correlation_id or new_correlation_id()
        self._base = {"correlation_id": self.correlation_id, **base_fields}

    def info(self, msg: str, **fields: Any) -> None:
        _emit("info", msg, **self._base, **fields)

    def error(self, msg: str, **fields: Any) -> None:
        _emit("error", msg, **self._base, **fields)
