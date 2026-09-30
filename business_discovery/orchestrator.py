from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from .controls import CircuitBreaker, RateLimiter, retry
from .models import SearchQuery, SearchRequest, Source, TaskResult
from .normalization import deduplicate
from .providers import BusinessDiscoveryProvider, ProviderError

logger = logging.getLogger(__name__)


class SearchOrchestrator:
    """In-process modular monolith orchestration; swap cache/store for distributed scale."""
    def __init__(self, providers: list[BusinessDiscoveryProvider], *, max_batch_size: int = 1000,
                 max_results: int = 100, max_concurrency: int = 10, cache_ttl_s: float = 300,
                 provider_rps: float = 5, provider_concurrency: int = 3, retry_attempts: int = 3):
        self.providers = {provider.name: provider for provider in providers}
        self.max_batch_size, self.max_results, self.cache_ttl_s = max_batch_size, max_results, cache_ttl_s
        self.global_semaphore = asyncio.Semaphore(max_concurrency)
        self.limiters = {name: RateLimiter(provider_rps, provider_concurrency) for name in self.providers}
        self.breakers = {name: CircuitBreaker() for name in self.providers}
        self.retry_attempts = retry_attempts
        self.cache: dict[str, tuple[float, list]] = {}
        self.inflight: dict[str, asyncio.Task[list]] = {}
        self._cache_lock = asyncio.Lock()

    def validate(self, request: SearchRequest) -> None:
        if not request.queries or len(request.queries) > self.max_batch_size:
            raise ValueError(f"queries must contain 1 to {self.max_batch_size} entries")
        for query in request.queries:
            query.validate(self.max_results)

    async def stream(self, request: SearchRequest) -> AsyncIterator[TaskResult]:
        self.validate(request)
        async def isolated(query: SearchQuery) -> TaskResult:
            try:
                return await self._search_one(query)
            except Exception as error:
                return TaskResult(task_id=str(uuid4()), query=query,
                    error={"code": "PROVIDER_ERROR", "message": str(error), "retryable": False})
        tasks = [asyncio.create_task(isolated(query), name=str(uuid4())) for query in request.queries]
        for future in asyncio.as_completed(tasks):
            yield await future

    async def search(self, request: SearchRequest) -> dict[str, Any]:
        started = time.monotonic()
        results, failures = [], []
        async for task in self.stream(request):
            (failures if task.error else results).append(task)
        companies = deduplicate([company for result in results for company in result.companies])
        return {"request_id": request.request_id, "status": "partial_success" if failures else "completed",
                "total_tasks": len(request.queries), "completed_tasks": len(results), "failed_tasks": len(failures),
                "results_count": len(companies), "results": [company.as_dict() for company in companies],
                "errors": [item.error for item in failures], "duration_ms": round((time.monotonic()-started)*1000, 2)}

    async def _search_one(self, query: SearchQuery) -> TaskResult:
        provider = self._choose_provider(query)
        key = self._key(provider.name, query)
        companies = await self._coalesced_search(key, provider, query)
        return TaskResult(task_id=str(uuid4()), query=query, companies=companies)

    def _choose_provider(self, query: SearchQuery) -> BusinessDiscoveryProvider:
        candidates = query.provider_preference or tuple(self.providers)
        for name in candidates:
            if name in self.providers:
                return self.providers[name]
        raise ProviderError("no configured provider supports this query")

    async def _coalesced_search(self, key: str, provider: BusinessDiscoveryProvider, query: SearchQuery) -> list:
        async with self._cache_lock:
            cached = self.cache.get(key)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            task = self.inflight.get(key)
            if task is None:
                task = asyncio.create_task(self._call_provider(provider, query))
                self.inflight[key] = task
        try:
            value = await task
            async with self._cache_lock:
                self.cache[key] = (time.monotonic() + self.cache_ttl_s, value)
            return value
        finally:
            async with self._cache_lock:
                if self.inflight.get(key) is task and task.done():
                    self.inflight.pop(key, None)

    async def _call_provider(self, provider: BusinessDiscoveryProvider, query: SearchQuery) -> list:
        breaker, limiter = self.breakers[provider.name], self.limiters[provider.name]
        async def call() -> list:
            breaker.before_call()
            async with self.global_semaphore, limiter:
                try:
                    records = await provider.search(query)
                    for record in records:
                        if not record.sources:
                            record.sources.append(Source(provider.name, record.id))
                    breaker.success()
                    return records[:query.max_results]
                except ProviderError:
                    breaker.failure()
                    raise
        return await retry(call, self.retry_attempts)

    @staticmethod
    def _key(provider: str, query: SearchQuery) -> str:
        raw = json.dumps({"provider": provider, **asdict(query)}, sort_keys=True, default=list)
        return hashlib.sha256(raw.encode()).hexdigest()
