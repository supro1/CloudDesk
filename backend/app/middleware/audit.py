from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.repositories import AuditLogRepository, ProfileRepository


class AuditMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.app = app
        self.session_factory = session_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method", "GET").upper() == "GET":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")[:12].upper()
        status_code = 500
        audit_written = False

        async def send_with_audit(message: Message) -> None:
            nonlocal status_code, audit_written
            if message["type"] == "http.response.start":
                status_code = message["status"]
                if not audit_written:
                    audit_written = True
                    await self._write_audit(scope, method, status_code)
            await send(message)

        try:
            await self.app(scope, receive, send_with_audit)
        except Exception:
            if not audit_written:
                audit_written = True
                await self._write_audit(scope, method, status_code)
            raise
        else:
            if not audit_written:
                await self._write_audit(scope, method, status_code)

    async def _write_audit(
        self,
        scope: Scope,
        method: str,
        status_code: int,
    ) -> None:
        state = scope.get("state", {})
        actor_id = state.get("actor_id")
        if not isinstance(actor_id, str):
            actor_id = None

        route_path = getattr(scope.get("route"), "path", None)
        if not isinstance(route_path, str):
            route_path = scope.get("path", "/")
        if not isinstance(route_path, str):
            route_path = "/"

        request_id = state.get("request_id")
        if not isinstance(request_id, str):
            request_id = None

        async with self.session_factory() as session:
            if actor_id is not None:
                profile = await ProfileRepository(session).get(actor_id)
                actor_id = profile.id if profile is not None else None

            await AuditLogRepository(session).create(
                actor_id=actor_id,
                request_id=request_id,
                action=f"http.{method.lower()}",
                method=method,
                path=route_path[:500],
                status_code=status_code,
                details={},
            )
            await session.commit()
