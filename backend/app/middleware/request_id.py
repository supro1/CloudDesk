from __future__ import annotations

import re
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.core.logging import request_id_context


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_REQUEST_ID_HEADER = b"x-request-id"


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._get_request_id(scope.get("headers", []))
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_context.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != _REQUEST_ID_HEADER
                ]
                headers.append((_REQUEST_ID_HEADER, request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_context.reset(token)

    @staticmethod
    def _get_request_id(headers: list[tuple[bytes, bytes]]) -> str:
        for name, value in headers:
            if name.lower() == _REQUEST_ID_HEADER:
                try:
                    candidate = value.decode("ascii")
                except UnicodeDecodeError:
                    break
                if _REQUEST_ID_PATTERN.fullmatch(candidate):
                    return candidate
                break
        return str(uuid4())
