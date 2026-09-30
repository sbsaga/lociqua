"""Reproducible synthetic benchmark. It never calls a live provider."""
import asyncio
import time

from business_discovery.models import SearchQuery, SearchRequest
from business_discovery.orchestrator import SearchOrchestrator
from business_discovery.providers import FixtureProvider


async def main() -> None:
    service = SearchOrchestrator([FixtureProvider()], max_concurrency=10)
    for count in (1, 3, 10, 50, 100):
        queries = tuple(SearchQuery("software companies", f"area-{i}") for i in range(count))
        start = time.perf_counter()
        output = await service.search(SearchRequest(queries))
        print({"tasks": count, "duration_ms": round((time.perf_counter()-start)*1000, 2),
               "results": output["results_count"]})

asyncio.run(main())
