"""Small dependency-free operational signals for the self-hosted service."""
from __future__ import annotations

import json
import logging
import time
from collections import Counter


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"), "level": record.levelname.lower(), "logger": record.name, "message": record.getMessage()}, sort_keys=True)


def configure_logging() -> None:
    handler = logging.StreamHandler(); handler.setFormatter(JsonFormatter())
    root = logging.getLogger(); root.handlers.clear(); root.addHandler(handler); root.setLevel(logging.INFO)


class Metrics:
    def __init__(self) -> None:
        self.started_at = time.monotonic(); self.requests: Counter[tuple[str, int]] = Counter()

    def record(self, route: str, status: int) -> None: self.requests[(route, status)] += 1

    def prometheus(self) -> bytes:
        lines = ["# HELP lociqua_uptime_seconds Seconds since process start.", "# TYPE lociqua_uptime_seconds gauge", f"lociqua_uptime_seconds {time.monotonic() - self.started_at:.3f}", "# HELP lociqua_http_requests_total HTTP responses by route and status.", "# TYPE lociqua_http_requests_total counter"]
        lines += [f'lociqua_http_requests_total{{route="{route}",status="{status}"}} {count}' for (route, status), count in sorted(self.requests.items())]
        return ("\n".join(lines) + "\n").encode()
