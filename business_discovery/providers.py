from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import Company, SearchQuery
from .storage import CompanyStore


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    pagination: bool = False
    radius: bool = False
    coordinates: bool = False
    stable_ids: bool = True


class BusinessDiscoveryProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    async def search(self, query: SearchQuery) -> list[Company]: ...


class ProviderError(Exception):
    """Provider failure with retry eligibility and optional Retry-After."""
    def __init__(self, message: str, retryable: bool = False, retry_after: float | None = None):
        super().__init__(message)
        self.retryable, self.retry_after = retryable, retry_after


class FixtureProvider:
    """Deterministic authorized provider for local development, tests, and benchmarks."""
    name = "fixture"
    capabilities = ProviderCapabilities(pagination=True, radius=True, coordinates=True)

    async def search(self, query: SearchQuery) -> list[Company]:
        slug = "-".join((query.keyword + " " + (query.location or "coordinates")).lower().split())
        return [Company(id=f"fixture:{slug}", name=f"{query.keyword.strip()} sample", locality=query.location,
                        categories=[query.keyword.strip()], sources=[])]


class LocalDatabaseProvider:
    """Primary real-world provider: data uploaded or owned by the deploying organization."""
    name = "local_database"
    capabilities = ProviderCapabilities(pagination=True, radius=False, coordinates=False)
    def __init__(self, store: CompanyStore): self.store = store
    async def search(self, query: SearchQuery) -> list[Company]:
        return self.store.search(query.keyword, query.location, query.max_results)
