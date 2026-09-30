"""Black-box checks for a running production stack; run after Docker startup."""
from __future__ import annotations
import os
import urllib.error
import urllib.request

BASE_URL = os.environ.get("LOCIQUA_TEST_URL", "http://127.0.0.1")

def request(path: str) -> tuple[int, dict[str, str]]:
    try:
        with urllib.request.urlopen(BASE_URL + path, timeout=5) as response: return response.status, dict(response.headers.items())
    except urllib.error.HTTPError as error: return error.code, dict(error.headers.items())

def check(path: str, expected: int) -> None:
    status, headers = request(path)
    assert status == expected, f"{path}: expected {expected}, received {status}"
    assert headers.get("X-Content-Type-Options") == "nosniff", f"{path}: missing nosniff header"

if __name__ == "__main__":
    check("/healthz", 200); check("/readyz", 200); check("/api/sources", 401)
    print("production smoke checks passed")
