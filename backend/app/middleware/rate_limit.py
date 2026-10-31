from __future__ import annotations

import logging
import time
from math import ceil

from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_RATE_LIMITED_BODY = b'{"detail":"Rate limit exceeded"}'
_UNAVAILABLE_BODY = b'{"detail":"Rate limiting service unavailable"}'
_RATE_LIMIT_HEADERS = {
    b"x-ratelimit-limit",
    b"x-ratelimit-remaining",
    b"x-ratelimit-reset",
}
_logger = logging.getLogger("clouddesk.middleware.rate_limit")


class RateLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        redis_client: Redis,
        limit: int,
        window_seconds: int = 60,
    ) -> None:
        self.app = app
        self.redis_client = redis_client
        self.limit = limit
        self.window_seconds = window_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_host = client[0] if client is not None else "unknown"
        now = time.time()
        window = int(now // self.window_seconds)
        reset_at = (window + 1) * self.window_seconds
        key = f"clouddesk:rate-limit:{client_host}:{window}"

        try:
            async with self.redis_client.pipeline(transaction=True) as pipeline:
                pipeline.set(key, 0, nx=True, ex=self.window_seconds)
                pipeline.incr(key)
                results = await pipeline.execute()
        except RedisError:
            _logger.warning("Redis rate-limit operation failed; rejecting request")
            await self._send_json(send, 503, _UNAVAILABLE_BODY)
            return

        count = int(results[1])
        remaining = max(0, self.limit - count)
        rate_headers = [
            (b"x-ratelimit-limit", str(self.limit).encode("ascii")),
            (b"x-ratelimit-remaining", str(remaining).encode("ascii")),
            (b"x-ratelimit-reset", str(reset_at).encode("ascii")),
        ]

        if count > self.limit:
            retry_after = max(1, ceil(reset_at - now))
            await self._send_json(
                send,
                429,
                _RATE_LIMITED_BODY,
                [
                    *rate_headers,
                    (b"retry-after", str(retry_after).encode("ascii")),
                ],
            )
            return

        async def send_with_rate_limit_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() not in _RATE_LIMIT_HEADERS
                ]
                message = {**message, "headers": [*headers, *rate_headers]}
            await send(message)

        await self.app(scope, receive, send_with_rate_limit_headers)

    @staticmethod
    async def _send_json(
        send: Send,
        status_code: int,
        body: bytes,
        headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        response_headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            *(headers or []),
        ]
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": response_headers,
            }
        )
        await send({"type": "http.response.body", "body": body})
