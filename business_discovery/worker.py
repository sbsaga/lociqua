"""Run with `python -m business_discovery.worker` in a separate worker container."""
from __future__ import annotations

import asyncio
import logging
import os
import time

from .api import build_service
from .jobs import SearchJobQueue
from .models import SearchQuery, SearchRequest
from .observability import configure_logging
from .alerts import AlertWebhook


def main() -> None:
    configure_logging(); queue = SearchJobQueue(); service = build_service(); alerts = AlertWebhook()
    logging.getLogger("lociqua.worker").info("worker_started")
    next_retention_check = 0.0
    while True:
        if time.monotonic() >= next_retention_check:
            next_retention_check = time.monotonic() + 60
            try:
                if hasattr(service.store, "purge_expired_evidence"):
                    removed = service.store.purge_expired_evidence()
                    if removed: logging.getLogger("lociqua.worker").info("evidence_retention_purged count=%s", removed)
            except Exception as error:
                logging.getLogger("lociqua.worker").exception("evidence_retention_failed")
                alerts.notify("evidence_retention_failed", {"error_type": type(error).__name__})
        item = queue.next()
        if not item:
            time.sleep(0.2)
            continue
        job_id, raw = item
        try:
            queries = tuple(SearchQuery(**query) for query in raw["queries"])
            result = asyncio.run(service.search(SearchRequest(queries, enrichment=bool(raw.get("enrichment")))))
            queue.complete(job_id, result)
        except Exception as error:
            logging.getLogger("lociqua.worker").exception("job_failed id=%s", job_id)
            queue.fail(job_id, error)
            alerts.notify("worker_job_failed", {"job_id": job_id, "error_type": type(error).__name__})


if __name__ == "__main__": main()
