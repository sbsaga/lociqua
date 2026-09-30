"""Password hashing and short-lived signed access tokens without a client-side dependency."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time


def hash_password(password: str, salt: str | None = None) -> str:
    if len(password) < 12: raise ValueError("password must be at least 12 characters")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310_000).hex()
    return f"pbkdf2_sha256$310000${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$", 3)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
        return algorithm == "pbkdf2_sha256" and hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError): return False


class TokenService:
    def __init__(self, secret: str):
        if len(secret) < 32: raise ValueError("LOCIQUA_AUTH_SECRET must contain at least 32 characters")
        self.secret = secret.encode()

    def issue(self, user_id: str, workspace_id: str, role: str, ttl_seconds: int = 3600) -> str:
        payload = {"sub": user_id, "workspace_id": workspace_id, "role": role, "exp": int(time.time()) + ttl_seconds}
        encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
        signature = hmac.new(self.secret, encoded, hashlib.sha256).digest()
        return (encoded + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode()

    def verify(self, token: str) -> dict[str, object] | None:
        try:
            encoded, signature = token.encode().split(b".", 1)
            expected = hmac.new(self.secret, encoded, hashlib.sha256).digest()
            if not hmac.compare_digest(expected, base64.urlsafe_b64decode(signature + b"=" * (-len(signature) % 4))): return None
            payload = json.loads(base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4)))
            return payload if int(payload["exp"]) >= time.time() else None
        except (ValueError, KeyError, TypeError, json.JSONDecodeError): return None
