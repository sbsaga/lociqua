"""Concurrent authenticated load check for search, CSV import, or queued jobs.

This is a controlled operational check, not an Internet-scale benchmark. Run it
against a disposable workspace when using import mode because it writes records.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import time
import urllib.error
import urllib.request

BASE = os.environ.get("LOCIQUA_TEST_URL", "http://127.0.0.1")
TOKEN = os.environ["LOCIQUA_TEST_TOKEN"]
MODE = os.environ.get("LOCIQUA_LOAD_MODE", "search")
COUNT = int(os.environ.get("LOCIQUA_LOAD_REQUESTS", "20"))
WORKERS = int(os.environ.get("LOCIQUA_LOAD_WORKERS", str(min(COUNT, 10))))
MAX_SECONDS = float(os.environ.get("LOCIQUA_LOAD_MAX_SECONDS", "30"))


def call(path: str, body: bytes, extra_headers: dict[str, str] | None = None) -> tuple[int, float, bytes]:
    headers = {"Authorization": "Bearer " + TOKEN, **(extra_headers or {})}
    request = urllib.request.Request(BASE + path, body, headers=headers, method="POST")
    began = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, time.monotonic() - began, response.read()
    except urllib.error.HTTPError as error:
        return error.code, time.monotonic() - began, error.read()


def search(_: int) -> tuple[int, float, bytes]:
    return call("/api/search", json.dumps({"queries": [{"keyword": "Analytics", "location": "Pune", "max_results": 5}]}).encode(), {"Content-Type": "application/json"})


def import_csv(index: int) -> tuple[int, float, bytes]:
    row = f"name,categories,city\nLoad Test {index},test,Pune\n".encode()
    return call("/api/import/csv", row, {"X-Source-Name": "load-test-authorized.csv", "Content-Type": "text/csv"})


def queued_job(_: int) -> tuple[int, float, bytes]:
    return call("/api/jobs/search", json.dumps({"queries": [{"keyword": "Analytics", "location": "Pune", "max_results": 5}]}).encode(), {"Content-Type": "application/json"})


if __name__ == "__main__":
    operations = {"search": search, "import": import_csv, "job": queued_job}
    if MODE not in operations: raise SystemExit("LOCIQUA_LOAD_MODE must be search, import, or job")
    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, WORKERS)) as pool:
        results = list(pool.map(operations[MODE], range(COUNT)))
    elapsed = time.monotonic() - started
    expected = 202 if MODE == "job" else (201 if MODE == "import" else 200)
    statuses = [status for status, _, _ in results]
    success = sum(status == expected for status in statuses)
    success_rate = success / COUNT
    p95 = sorted(latency for _, latency, _ in results)[max(0, int(COUNT * .95) - 1)]
    assert success_rate == 1, f"expected {expected}; statuses={statuses}"
    assert elapsed <= MAX_SECONDS, f"run exceeded {MAX_SECONDS}s: {elapsed:.2f}s"
    assert p95 <= MAX_SECONDS, f"p95 request latency exceeded {MAX_SECONDS}s: {p95:.2f}s"
    print(f"load check passed mode={MODE} requests={COUNT} success_rate={success_rate:.0%} elapsed={elapsed:.2f}s p95={p95:.2f}s")
