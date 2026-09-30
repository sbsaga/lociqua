"""Redis-backed durable jobs for long-running search batches."""
from __future__ import annotations

import json
import os
import time
from uuid import uuid4

import redis

QUEUE = "lociqua:search-jobs"


class SearchJobQueue:
    def __init__(self, url: str | None = None):
        self.client = redis.Redis.from_url(url or os.environ["REDIS_URL"], decode_responses=True)

    def enqueue(self, payload: dict[str, object]) -> str:
        job_id = str(uuid4()); key = f"lociqua:job:{job_id}"
        self.client.hset(key, mapping={"status": "queued", "payload": json.dumps(payload), "created_at": str(time.time())})
        self.client.expire(key, 86_400); self.client.rpush(QUEUE, job_id)
        return job_id

    def get(self, job_id: str) -> dict[str, object] | None:
        data = self.client.hgetall(f"lociqua:job:{job_id}")
        if not data: return None
        result = {"id": job_id, "status": data["status"]}
        if "result" in data: result["result"] = json.loads(data["result"])
        if "error" in data: result["error"] = data["error"]
        return result

    def next(self, timeout: int = 5) -> tuple[str, dict[str, object]] | None:
        item = self.client.blpop(QUEUE, timeout=timeout)
        if not item: return None
        job_id = item[1]; data = self.client.hgetall(f"lociqua:job:{job_id}")
        if not data: return None
        self.client.hset(f"lociqua:job:{job_id}", mapping={"status": "running", "started_at": str(time.time())})
        return job_id, json.loads(data["payload"])

    def complete(self, job_id: str, result: dict[str, object]) -> None:
        self.client.hset(f"lociqua:job:{job_id}", mapping={"status": "completed", "result": json.dumps(result), "completed_at": str(time.time())})

    def fail(self, job_id: str, error: Exception) -> None:
        self.client.hset(f"lociqua:job:{job_id}", mapping={"status": "failed", "error": str(error), "completed_at": str(time.time())})
