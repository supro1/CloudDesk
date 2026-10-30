from __future__ import annotations

import asyncio
import json
import logging
import unittest
from typing import Any

from fastapi import Request

from backend.app.core.config import Settings
from backend.app.core.logging import JsonFormatter
from backend.app.main import create_app


async def asgi_get(
    app: Any,
    path: str,
    headers: list[tuple[bytes, bytes]] | None = None,
    expected_exception: type[Exception] | None = None,
) -> tuple[int, dict[bytes, bytes], bytes]:
    response_start: dict[str, Any] = {}
    response_body = bytearray()
    request_sent = False

    async def receive() -> dict[str, Any]:
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            response_start.update(message)
        elif message["type"] == "http.response.body":
            response_body.extend(message.get("body", b""))

    encoded_path = path.encode("ascii")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": encoded_path,
        "query_string": b"",
        "root_path": "",
        "headers": headers or [],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    try:
        await app(scope, receive, send)
    except Exception as error:
        if expected_exception is None or not isinstance(error, expected_exception):
            raise
    response_headers = dict(response_start.get("headers", []))
    return response_start["status"], response_headers, bytes(response_body)


class HealthRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(Settings(_env_file=None))

    def test_liveness_routes_respond_without_dependency_checks(self) -> None:
        for path in ("/health", "/health/live"):
            status, _, body = asyncio.run(asgi_get(self.app, path))
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body), {"status": "ok"})

    def test_readiness_reports_configured_checks(self) -> None:
        status, _, body = asyncio.run(asgi_get(self.app, "/health/ready"))

        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(body),
            {"status": "ok", "checks": {"application": "ok"}},
        )

    def test_failed_readiness_check_returns_service_unavailable(self) -> None:
        app = create_app(
            Settings(_env_file=None),
            readiness_checks={"database": lambda: False},
        )
        status, _, body = asyncio.run(asgi_get(app, "/health/ready"))

        self.assertEqual(status, 503)
        self.assertEqual(
            json.loads(body),
            {"status": "unavailable", "checks": {"database": "error"}},
        )

    def test_request_id_is_preserved_and_generated_when_missing(self) -> None:
        status, headers, _ = asyncio.run(
            asgi_get(
                self.app,
                "/health/live",
                headers=[(b"x-request-id", b"client-request-123")],
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"x-request-id"], b"client-request-123")

        _, generated_headers, _ = asyncio.run(asgi_get(self.app, "/health/live"))
        generated_id = generated_headers[b"x-request-id"].decode("ascii")
        self.assertRegex(generated_id, r"^[0-9a-f-]{36}$")

    def test_invalid_request_id_is_replaced(self) -> None:
        _, headers, _ = asyncio.run(
            asgi_get(
                self.app,
                "/health/live",
                headers=[(b"x-request-id", b"bad\r\nvalue")],
            )
        )

        self.assertNotEqual(headers[b"x-request-id"], b"bad\r\nvalue")

    def test_unhandled_errors_keep_the_request_id(self) -> None:
        async def fail() -> None:
            raise RuntimeError("test failure")

        self.app.add_api_route("/test/error", fail)
        status, headers, _ = asyncio.run(
            asgi_get(
                self.app,
                "/test/error",
                headers=[(b"x-request-id", b"error-request-789")],
                expected_exception=RuntimeError,
            )
        )

        self.assertEqual(status, 500)
        self.assertEqual(headers[b"x-request-id"], b"error-request-789")

    def test_request_id_is_included_in_structured_logs(self) -> None:
        async def inspect_request_context(request: Request) -> dict[str, Any]:
            record = logging.LogRecord(
                name="clouddesk.api",
                level=20,
                pathname=__file__,
                lineno=1,
                msg="Request completed",
                args=(),
                exc_info=None,
            )
            return {
                "request_id": request.state.request_id,
                "log": json.loads(JsonFormatter().format(record)),
            }

        self.app.add_api_route("/test/request-context", inspect_request_context)
        status, headers, body = asyncio.run(
            asgi_get(
                self.app,
                "/test/request-context",
                headers=[(b"x-request-id", b"log-request-456")],
            )
        )

        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"x-request-id"], b"log-request-456")
        self.assertEqual(payload["request_id"], "log-request-456")
        self.assertEqual(payload["log"]["request_id"], "log-request-456")

    def test_cors_exposes_request_id_header(self) -> None:
        status, headers, _ = asyncio.run(
            asgi_get(
                self.app,
                "/health/live",
                headers=[(b"origin", b"http://localhost:3000")],
            )
        )

        self.assertEqual(status, 200)
        self.assertIn(b"x-request-id", headers[b"access-control-expose-headers"].lower())


if __name__ == "__main__":
    unittest.main()
