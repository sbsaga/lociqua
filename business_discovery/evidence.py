"""Validation and policy helpers for user-assisted web evidence.

This module intentionally contains no HTTP fetching or browser automation.
Evidence is submitted only after a person has viewed a page and confirmed the
selected fields in the companion browser extension.
"""
from __future__ import annotations

import hashlib
import json
from urllib.parse import urlparse

CAPTURE_FIELDS = frozenset({
    "name", "description", "categories", "website", "phone", "email", "address",
    "locality", "city", "state", "country", "postal_code",
})
CONNECTOR_TYPES = frozenset({"browser_capture", "csv", "official_api", "licensed_feed", "open_data", "manual"})
POLICY_STATUSES = frozenset({"draft", "approved", "paused", "blocked"})
EVIDENCE_STATUSES = frozenset({"pending", "approved", "rejected", "needs_correction", "stale"})
TASK_STATUSES = frozenset({"not_started", "in_review", "completed", "blocked", "needs_clarification"})


def canonical_domain(value: str) -> str:
    candidate = value.strip().lower()
    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("domain must be a plain HTTP(S) hostname")
    return parsed.hostname.rstrip(".")


def capture_url(value: str) -> tuple[str, str]:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("capture_url must be an absolute HTTP(S) URL without credentials")
    if len(value) > 2_000:
        raise ValueError("capture_url must not exceed 2000 characters")
    return parsed.geturl(), parsed.hostname.lower().rstrip(".")


def domain_matches(policy_domain: str, observed_domain: str) -> bool:
    return observed_domain == policy_domain or observed_domain.endswith("." + policy_domain)


def validate_fields(raw: object, allowed_fields: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError("fields must be an object")
    allowed = set(allowed_fields or CAPTURE_FIELDS)
    invalid = set(raw) - CAPTURE_FIELDS
    disallowed = set(raw) - allowed
    if invalid:
        raise ValueError(f"unsupported captured fields: {', '.join(sorted(invalid))}")
    if disallowed:
        raise ValueError(f"source policy does not allow: {', '.join(sorted(disallowed))}")
    cleaned: dict[str, object] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            value = value.strip()
            if len(value) > 2_000:
                raise ValueError(f"{key} exceeds 2000 characters")
            if value:
                cleaned[key] = value
        elif key == "categories" and isinstance(value, list) and all(isinstance(item, str) and len(item) <= 100 for item in value):
            cleaned[key] = [item.strip() for item in value if item.strip()][:20]
        else:
            raise ValueError(f"{key} must be text" + (" or a list of text" if key == "categories" else ""))
    if not cleaned.get("name"):
        raise ValueError("a non-empty company name is required")
    return cleaned


def content_fingerprint(url: str, fields: dict[str, object]) -> str:
    canonical = json.dumps({"url": url, "fields": fields}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()
