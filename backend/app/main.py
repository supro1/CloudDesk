from __future__ import annotations

from collections.abc import Mapping

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.health import HealthCheck, router as health_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import setup_logging
from backend.app.middleware.request_id import RequestIdMiddleware


def create_app(
    settings: Settings | None = None,
    readiness_checks: Mapping[str, HealthCheck] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="CloudDesk Support API")
    app.state.readiness_checks = (
        readiness_checks if readiness_checks is not None else {"application": lambda: True}
    )
    app.include_router(health_router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    # Wrap the full stack so IDs are also attached to Starlette-generated 500 responses.
    app.middleware_stack = RequestIdMiddleware(app.build_middleware_stack())
    return app


app = create_app()
