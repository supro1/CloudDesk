from __future__ import annotations

from unittest.mock import patch

from fakeredis.aioredis import FakeRedis
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.types import Message, Receive, Scope, Send

from backend.app.core.config import Settings
from backend.app.core.redis import create_redis_client
from backend.app.main import create_app
from backend.app.middleware.rate_limit import RateLimitMiddleware


async def _ok_app(_scope: Scope, _receive: Receive, send: Send) -> None:
    assert _scope["type"] == "http"
    await _receive()
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-length", b"2")],
        }
    )
    await send({"type": "http.response.body", "body": b"ok"})


async def _request(
    app: RateLimitMiddleware,
    client_host: str,
) -> tuple[int, dict[bytes, bytes], bytes]:
    messages: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": (client_host, 50000),
        "server": ("testserver", 80),
    }

    await app(scope, receive, send)
    start = messages[0]
    body = messages[1].get("body", b"")
    return start["status"], dict(start.get("headers", [])), body


async def test_rate_limit_has_per_client_fixed_window_and_retry_after() -> None:
    redis_client = FakeRedis()
    limiter = RateLimitMiddleware(_ok_app, redis_client, limit=2)

    first = await _request(limiter, "192.0.2.1")
    second = await _request(limiter, "192.0.2.1")
    blocked = await _request(limiter, "192.0.2.1")
    another_client = await _request(limiter, "192.0.2.2")
    await redis_client.aclose()

    assert [first[0], second[0], blocked[0], another_client[0]] == [
        200,
        200,
        429,
        200,
    ]
    assert blocked[2] == b'{"detail":"Rate limit exceeded"}'
    assert blocked[1][b"x-ratelimit-limit"] == b"2"
    assert blocked[1][b"x-ratelimit-remaining"] == b"0"
    assert 1 <= int(blocked[1][b"retry-after"]) <= 60


async def test_redis_failure_rejects_request_with_service_unavailable() -> None:
    redis_client = FakeRedis()
    limiter = RateLimitMiddleware(_ok_app, redis_client, limit=2)
    with patch.object(
        redis_client,
        "pipeline",
        side_effect=RedisError("redis unavailable"),
    ):
        response = await _request(limiter, "192.0.2.1")
    await redis_client.aclose()

    assert response[0] == 503
    assert response[2] == b'{"detail":"Rate limiting service unavailable"}'


async def test_real_redis_client_uses_configured_url() -> None:
    redis_client = create_redis_client(
        Settings(
            _env_file=None,
            use_fake_redis=False,
            redis_url="redis://localhost:6379/0",
        )
    )
    assert isinstance(redis_client, Redis)
    await redis_client.aclose()


def test_create_app_enforces_configured_limit_and_preserves_request_id() -> None:
    settings = Settings(
        _env_file=None,
        demo_mode=False,
        use_fake_redis=True,
        rate_limit_per_minute=1,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        first = client.get(
            "/health/live",
            headers={"X-Request-ID": "rate-limit-first"},
        )
        blocked = client.get(
            "/health/live",
            headers={"X-Request-ID": "rate-limit-second"},
        )

    assert first.status_code == 200
    assert first.headers["x-ratelimit-limit"] == "1"
    assert blocked.status_code == 429
    assert blocked.headers["x-request-id"] == "rate-limit-second"
    assert blocked.headers["retry-after"]
