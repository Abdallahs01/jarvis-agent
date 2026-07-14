"""
Structured logging setup.

Emits one JSON object per log line rather than freeform text — the
standard shape expected by production log aggregators (CloudWatch,
Datadog, Grafana Loki, or Render's own log viewer, which highlights
JSON fields automatically). Configured once at startup via
configure_logging().
"""
import json
import logging
import sys

_RESERVED_LOG_RECORD_KEYS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Extra fields passed via logger.info("msg", extra={...}) are
        # merged in as their own JSON keys, so callers attach structured
        # context (tool name, conversation_id, duration_ms, ...) instead
        # of string-formatting it into the message text.
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_RECORD_KEYS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Quiet noisy third-party loggers so our own structured logs aren't
    # drowned out by every outbound HTTP connection detail.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
