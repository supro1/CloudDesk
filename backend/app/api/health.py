from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)
HealthCheck = Callable[[], bool | Awaitable[bool]]
router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    checks: Mapping[str, HealthCheck] = request.app.state.readiness_checks
    results: dict[str, str] = {}

    for name, check in checks.items():
        try:
            result = check()
            if isinstance(result, Awaitable):
                result = await result
            results[name] = "ok" if result else "error"
        except Exception:
            logger.exception("Readiness check failed", extra={"health_check": name})
            results[name] = "error"

    ready = all(result == "ok" for result in results.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ok" if ready else "unavailable", "checks": results},
    )
