from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class SearchQuery:
    keyword: str
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_m: int | None = None
    country: str | None = None
    language: str | None = None
    max_results: int = 25
    provider_preference: tuple[str, ...] = ()

    def validate(self, max_results: int) -> None:
        if not self.keyword.strip():
            raise ValueError("keyword is required")
        if not self.location and (self.latitude is None or self.longitude is None):
            raise ValueError("location or both coordinates are required")
        if not 1 <= self.max_results <= max_results:
            raise ValueError(f"max_results must be between 1 and {max_results}")
        if self.radius_m is not None and not 1 <= self.radius_m <= 100_000:
            raise ValueError("radius_m must be between 1 and 100000")


@dataclass(frozen=True, slots=True)
class SearchRequest:
    queries: tuple[SearchQuery, ...]
    enrichment: bool = False
    request_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(slots=True)
class Source:
    provider: str
    provider_record_id: str
    source_url: str | None = None
    discovered_at: str = field(default_factory=utcnow)


@dataclass(slots=True)
class Company:
    id: str
    name: str
    description: str | None = None
    categories: list[str] = field(default_factory=list)
    website: str | None = None
    domain: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    sources: list[Source] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TaskResult:
    task_id: str
    query: SearchQuery
    companies: list[Company] = field(default_factory=list)
    error: dict[str, Any] | None = None
