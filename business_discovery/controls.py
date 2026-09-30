from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from .providers import ProviderError

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(ProviderError):
    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    reset_after_s: float = 30
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    opened_at: float = 0

    def before_call(self) -> None:
        if self.state is CircuitState.OPEN:
            if time.monotonic() - self.opened_at < self.reset_after_s:
                raise CircuitOpenError("provider circuit is open")
            self.state = CircuitState.HALF_OPEN

    def success(self) -> None:
        self.state, self.failures = CircuitState.CLOSED, 0

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state, self.opened_at = CircuitState.OPEN, time.monotonic()


class RateLimiter:
    """Simple monotonic rate gate plus bounded in-flight requests."""
    def __init__(self, requests_per_second: float, concurrency: int):
        self.interval = 1 / requests_per_second if requests_per_second > 0 else 0
        self._next_at, self._lock = 0.0, asyncio.Lock()
        self.semaphore = asyncio.Semaphore(concurrency)

    async def __aenter__(self):
        await self.semaphore.acquire()
        async with self._lock:
            delay = self._next_at - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_at = time.monotonic() + self.interval
        return self

    async def __aexit__(self, *_: object) -> None:
        self.semaphore.release()


async def retry(operation: Callable[[], Awaitable[T]], attempts: int, base_delay_s: float = .25) -> T:
    for attempt in range(attempts):
        try:
            return await operation()
        except ProviderError as error:
            if not error.retryable or attempt == attempts - 1:
                raise
            delay = error.retry_after if error.retry_after is not None else base_delay_s * 2 ** attempt
            await asyncio.sleep(delay + random.uniform(0, delay * .2))
    raise AssertionError("unreachable")
