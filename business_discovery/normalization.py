from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import Company


def normalize_company(company: Company) -> Company:
    company.name = " ".join(company.name.split())
    company.phone = re.sub(r"[^0-9+]", "", company.phone) if company.phone else None
    if company.website:
        parsed = urlparse(company.website if "://" in company.website else "https://" + company.website)
        company.domain = parsed.hostname.lower().removeprefix("www.") if parsed.hostname else None
        company.website = parsed.geturl()
    company.categories = sorted({" ".join(item.split()).lower() for item in company.categories})
    return company


def identity_key(company: Company) -> tuple[str, str]:
    if company.sources and company.sources[0].provider_record_id:
        return ("source", f"{company.sources[0].provider}:{company.sources[0].provider_record_id}")
    if company.domain:
        return ("domain", company.domain)
    if company.phone:
        return ("phone", company.phone)
    return ("name_location", f"{company.name.lower()}|{(company.locality or company.city or '').lower()}")


def deduplicate(companies: list[Company]) -> list[Company]:
    seen: dict[tuple[str, str], Company] = {}
    for item in companies:
        item = normalize_company(item)
        key = identity_key(item)
        if key in seen:
            existing = seen[key]
            existing.sources.extend(source for source in item.sources if source not in existing.sources)
        else:
            seen[key] = item
    return list(seen.values())
