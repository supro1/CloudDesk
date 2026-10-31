from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
from fakeredis.aioredis import FakeRedis
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import Message, Receive, Scope, Send

from backend.app.core.config import Settings
from backend.app.core.database import create_database_engine, create_tables
from backend.app.main import create_app
from backend.app.middleware.audit import AuditMiddleware
from backend.app.middleware.rate_limit import RateLimitMiddleware
from backend.app.middleware.request_id import RequestIdMiddleware
from backend.app.models.entities import AuditLog, Profile

ACTOR_ID = "00000000-0000-4000-8000-000000000001"


async def _call_middleware(
    middleware: AuditMiddleware,
    method: str,
    path: str = "/api/v1/tickets/123",
) -> list[Message]:
    messages: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"token=must-not-be-recorded",
        "root_path": "",
        "headers": [(b"x-request-id", b"audit-request-123")],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "state": {"request_id": "audit-request-123"},
    }

    await middleware(scope, receive, send)
    return messages


@pytest.fixture
async def audit_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            Profile(
                id=ACTOR_ID,
                email="agent@example.test",
                display_name="Test Agent",
                role="agent",
                is_active=True,
            )
        )
        await session.commit()
    yield session_factory
    await engine.dispose()


async def test_non_get_requests_are_audited_without_sensitive_url_data(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def endpoint(scope: Scope, _receive: Receive, send: Send) -> None:
        scope.setdefault("state", {})["actor_id"] = ACTOR_ID
        scope["route"] = SimpleNamespace(path="/api/v1/tickets/{ticket_id}")
        await send(
            {
                "type": "http.response.start",
                "status": 202,
                "headers": [(b"content-length", b"0")],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    middleware = AuditMiddleware(endpoint, audit_session_factory)
    await _call_middleware(middleware, "POST")
    await _call_middleware(middleware, "GET")

    async with audit_session_factory() as session:
        audits = list((await session.scalars(select(AuditLog))).all())

    assert len(audits) == 1
    audit = audits[0]
    assert audit.actor_id == ACTOR_ID
    assert audit.request_id == "audit-request-123"
    assert audit.action == "http.post"
    assert audit.method == "POST"
    assert audit.path == "/api/v1/tickets/{ticket_id}"
    assert audit.status_code == 202
    assert audit.details == {}


async def test_unhandled_request_errors_are_audited_as_server_errors(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def endpoint(_scope: Scope, _receive: Receive, _send: Send) -> None:
        raise RuntimeError("request failed")

    middleware = AuditMiddleware(endpoint, audit_session_factory)
    with pytest.raises(RuntimeError, match="request failed"):
        await _call_middleware(middleware, "POST")

    async with audit_session_factory() as session:
        audit = await session.scalar(select(AuditLog))

    assert audit is not None
    assert audit.status_code == 500


async def test_rate_limit_rejections_are_audited(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def endpoint(_scope: Scope, _receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-length", b"0")],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    redis_client = FakeRedis()
    rate_limiter = RateLimitMiddleware(endpoint, redis_client, limit=1)
    middleware = AuditMiddleware(rate_limiter, audit_session_factory)
    try:
        await _call_middleware(middleware, "POST")
        await _call_middleware(middleware, "POST")
    finally:
        await redis_client.aclose()

    async with audit_session_factory() as session:
        statuses = sorted(await session.scalars(select(AuditLog.status_code)))

    assert statuses == [200, 429]


def test_app_builds_audit_around_cors_and_rate_limit() -> None:
    app = create_app(Settings(_env_file=None, use_fake_redis=True))

    assert [middleware.cls for middleware in app.user_middleware] == [
        AuditMiddleware,
        CORSMiddleware,
        RateLimitMiddleware,
    ]
    assert isinstance(app.middleware_stack, RequestIdMiddleware)
