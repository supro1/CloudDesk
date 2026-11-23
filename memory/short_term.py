from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

SHORT_TERM_TTL_SECONDS = 24 * 60 * 60
RETRIEVAL_CACHE_TTL_SECONDS = 5 * 60


class ShortTermMemory:
    """Namespaced, expiring storage for ticket and workflow runtime data."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def get_conversation(self, ticket_id: str) -> list[dict[str, Any]] | None:
        value = await self._get_json(f"memory:ticket:{ticket_id}:conversation")
        if value is None:
            return None
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise TypeError("Stored conversation must be a list of message objects")
        return value

    async def set_conversation(
        self,
        ticket_id: str,
        messages: list[dict[str, Any]],
    ) -> None:
        await self._set_json(
            f"memory:ticket:{ticket_id}:conversation",
            messages,
            SHORT_TERM_TTL_SECONDS,
        )

    async def get_workflow_state(self, workflow_id: str) -> dict[str, Any] | None:
        value = await self._get_json(f"memory:workflow:{workflow_id}:state")
        if value is None:
            return None
        if not isinstance(value, dict):
            raise TypeError("Stored workflow state must be an object")
        return value

    async def set_workflow_state(
        self,
        workflow_id: str,
        state: dict[str, Any],
    ) -> None:
        await self._set_json(
            f"memory:workflow:{workflow_id}:state",
            state,
            SHORT_TERM_TTL_SECONDS,
        )

    async def get_retrieval_cache(
        self,
        *,
        mode: str,
        category: str,
        top_k: int,
        query: str,
    ) -> Any | None:
        return await self._get_json(self._retrieval_key(mode, category, top_k, query))

    async def set_retrieval_cache(
        self,
        value: Any,
        *,
        mode: str,
        category: str,
        top_k: int,
        query: str,
    ) -> None:
        await self._set_json(
            self._retrieval_key(mode, category, top_k, query),
            value,
            RETRIEVAL_CACHE_TTL_SECONDS,
        )

    async def _get_json(self, key: str) -> Any | None:
        value = await self.redis.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError(f"Stored memory value for {key!r} is not valid JSON") from error

    async def _set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        await self.redis.set(key, encoded, ex=ttl_seconds)

    @staticmethod
    def _retrieval_key(mode: str, category: str, top_k: int, query: str) -> str:
        return f"rag:{mode}:{category}:{top_k}:{query}"


__all__ = [
    "RETRIEVAL_CACHE_TTL_SECONDS",
    "SHORT_TERM_TTL_SECONDS",
    "ShortTermMemory",
]
