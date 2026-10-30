from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in ("request_id", "workflow_id"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: int | str = "INFO") -> None:
    if isinstance(level, str):
        resolved_level = logging.getLevelNamesMapping().get(level.upper())
        if resolved_level is None:
            raise ValueError(f"Unknown logging level: {level}")
    elif isinstance(level, int):
        resolved_level = level
    else:
        raise TypeError("Logging level must be a string or integer")

    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)
    if not root_logger.handlers:
        root_logger.addHandler(logging.StreamHandler())

    for handler in root_logger.handlers:
        handler.setLevel(resolved_level)
        handler.setFormatter(JsonFormatter())
