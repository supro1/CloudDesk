from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.auth import router as auth_router
from backend.app.api.health import HealthCheck
from backend.app.api.health import router as health_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.database import create_tables, dispose_engine, session_factory
from backend.app.core.logging import setup_logging
from backend.app.core.redis import create_redis_client
from backend.app.middleware.rate_limit import RateLimitMiddleware
from backend.app.middleware.request_id import RequestIdMiddleware
from backend.app.services.seed_service import bootstrap_demo_data


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        await create_tables()
        settings: Settings = app.state.settings
        if settings.demo_mode:
            async with session_factory() as session:
                await bootstrap_demo_data(session, settings.sample_data_dir)
        yield
    finally:
        try:
            await dispose_engine()
        finally:
            await app.state.redis_client.aclose()


def create_app(
    settings: Settings | None = None,
    readiness_checks: Mapping[str, HealthCheck] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="CloudDesk Support API", lifespan=lifespan)
    app.state.settings = settings
    redis_client = create_redis_client(settings)
    app.state.redis_client = redis_client
    app.state.readiness_checks = (
        readiness_checks if readiness_checks is not None else {"application": lambda: True}
    )
    app.include_router(auth_router)
    app.include_router(health_router)

    app.add_middleware(
        RateLimitMiddleware,
        redis_client=redis_client,
        limit=settings.rate_limit_per_minute,
    )
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
