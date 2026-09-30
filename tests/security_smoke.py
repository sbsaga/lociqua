"""Black-box authentication and HTTP-hardening checks for a running stack.

Set LOCIQUA_TEST_TOKEN to an owner/editor bearer token.  Optionally set
LOCIQUA_VIEWER_TOKEN to verify that read-only users cannot write.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("LOCIQUA_TEST_URL", "http://127.0.0.1")
OWNER_TOKEN = os.environ.get("LOCIQUA_TEST_TOKEN", "")
VIEWER_TOKEN = os.environ.get("LOCIQUA_VIEWER_TOKEN", "")


def request(path: str, method: str = "GET", token: str = "", body: bytes | None = None) -> tuple[int, dict[str, str]]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if body is not None: headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response: return response.status, dict(response.headers.items())
    except urllib.error.HTTPError as error: return error.code, dict(error.headers.items())


def assert_headers(headers: dict[str, str]) -> None:
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")


if __name__ == "__main__":
    status, headers = request("/api/sources")
    assert status == 401, status; assert_headers(headers)
    status, headers = request("/api/search", "POST", body=b"{}")
    assert status == 401, status; assert_headers(headers)
    if OWNER_TOKEN:
        status, _ = request("/api/search", "POST", OWNER_TOKEN, b"{" + b"x" * 1_000_001 + b"}")
        assert status == 413, status
    if VIEWER_TOKEN:
        payload = json.dumps({"queries": [{"keyword": "clinic", "location": "Pune"}]}).encode()
        status, _ = request("/api/search", "POST", VIEWER_TOKEN, payload)
        assert status == 403, status
    print("security smoke checks passed")
