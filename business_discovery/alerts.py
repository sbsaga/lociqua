"""Optional, generic outbound operational webhook alerts.

Alerts are disabled unless LOCIQUA_ALERT_WEBHOOK_URL is configured.  This module
intentionally has no vendor SDK or default destination, so operators retain
control of data residency and notification routing.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class AlertWebhook:
    """Best-effort alert sender with per-event throttling; never blocks requests."""

    def __init__(self, url: str | None = None, cooldown_seconds: int = 300) -> None:
        self.url = url if url is not None else os.environ.get("LOCIQUA_ALERT_WEBHOOK_URL", "")
        parsed = urlparse(self.url) if self.url else None
        if self.url and (not parsed or parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password):
            raise ValueError("LOCIQUA_ALERT_WEBHOOK_URL must be an HTTPS URL without embedded credentials")
        self.cooldown_seconds = cooldown_seconds
        self._last_sent: dict[str, float] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def notify(self, event: str, details: dict[str, object] | None = None) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        if now - self._last_sent.get(event, 0) < self.cooldown_seconds:
            return
        self._last_sent[event] = now
        payload = {"service": "lociqua", "event": event, "timestamp": int(time.time()), "details": details or {}}
        thread = threading.Thread(target=self._post, args=(payload,), daemon=True)
        thread.start()

    def _post(self, payload: dict[str, object]) -> None:
        try:
            request = Request(self.url, data=json.dumps(payload, separators=(",", ":")).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "Lociqua-Alert/1"}, method="POST")
            with urlopen(request, timeout=5) as response:
                if response.status >= 300:
                    raise RuntimeError(f"webhook returned {response.status}")
        except Exception:
            # Never log the URL, payload content, credentials, or headers.
            logging.getLogger("lociqua.alerts").exception("alert_delivery_failed event=%s", payload["event"])
