from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def validate_public_url(value: str) -> str:
    """Reject URL schemes and resolved targets unsafe for optional enrichment."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("only credential-free http(s) URLs are allowed")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, None)}
    except socket.gaierror as error:
        raise ValueError("URL host cannot be resolved") from error
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("private, loopback, link-local, and reserved targets are forbidden")
    return value
