from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from agents.checkpointer import open_checkpointer
from agents.graph import create_support_graph
from backend.app.api.auth import router as auth_router
from backend.app.api.customers import router as customers_router
from backend.app.api.health import HealthCheck
from backend.app.api.health import router as health_router
from backend.app.api.knowledge import router as knowledge_router
from backend.app.api.tickets import router as tickets_router
from backend.app.api.workflow import router as workflow_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.database import (
    create_tables,
    dispose_engine,
    get_session,
    session_factory,
)
from backend.app.core.logging import setup_logging
from backend.app.core.redis import create_redis_client
from backend.app.middleware.audit import AuditMiddleware
from backend.app.middleware.rate_limit import RateLimitMiddleware
from backend.app.middleware.request_id import RequestIdMiddleware
from backend.app.services.knowledge_service import KnowledgeService
from backend.app.services.seed_service import bootstrap_demo_data
from backend.app.services.workflow_service import WorkflowService
from backend.app.tools.factory import create_support_tool_registry
from integrations import create_mock_integrations
from rag.embeddings import FakeEmbeddings
from rag.vector_store import create_vector_store


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app_session_factory: async_sessionmaker[AsyncSession] = (
        app.state.database_session_factory
    )
    is_custom_database = app.state.custom_database_session_factory
    try:
        bound_engine = getattr(app_session_factory, "kw", {}).get("bind")
        if isinstance(bound_engine, AsyncEngine):
            await create_tables(bound_engine)
        else:
            await create_tables()
        settings: Settings = app.state.settings
        if settings.demo_mode:
            async with app_session_factory() as session:
                await bootstrap_demo_data(session, settings.sample_data_dir)
        vector_store = await create_vector_store(settings)
        app.state.knowledge_service = KnowledgeService(
            vector_store,
            FakeEmbeddings(dimensions=settings.embedding_dimensions),
        )
        app.state.integrations = create_mock_integrations()
        app.state.tool_registry = create_support_tool_registry(
            app_session_factory,
            app.state.knowledge_service,
            integrations=app.state.integrations,
            settings=settings,
        )
        async with AsyncExitStack() as stack:
            checkpointer = await stack.enter_async_context(
                open_checkpointer(settings.checkpoint_db_path)
            )
            app.state.workflow_graph = create_support_graph(
                app.state.tool_registry,
                app_session_factory,
                checkpointer=checkpointer,
            )
            app.state.workflow_service = WorkflowService(
                app_session_factory,
                app.state.workflow_graph,
            )
            yield
    finally:
        try:
            knowledge_service: KnowledgeService | None = getattr(
                app.state, "knowledge_service", None
            )
            if knowledge_service is not None:
                await knowledge_service.close()
        finally:
            try:
                if not is_custom_database:
                    await dispose_engine()
            finally:
                await app.state.redis_client.aclose()


def create_app(
    settings: Settings | None = None,
    readiness_checks: Mapping[str, HealthCheck] | None = None,
    *,
    database_session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="CloudDesk Support API", lifespan=lifespan)
    app.state.settings = settings
    app.state.database_session_factory = database_session_factory or session_factory
    app.state.custom_database_session_factory = database_session_factory is not None
    if database_session_factory is not None:
        async def override_session() -> AsyncIterator[AsyncSession]:
            async with database_session_factory() as session:
                yield session

        app.dependency_overrides[get_session] = override_session
    redis_client = create_redis_client(settings)
    app.state.redis_client = redis_client
    app.state.readiness_checks = (
        readiness_checks if readiness_checks is not None else {"application": lambda: True}
    )
    app.include_router(auth_router)
    app.include_router(customers_router)
    app.include_router(knowledge_router)
    app.include_router(tickets_router)
    app.include_router(workflow_router)
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
    # Keep audit outside CORS and rate limiting so short-circuited responses are recorded.
    app.add_middleware(
        AuditMiddleware,
        session_factory=app.state.database_session_factory,
    )
    # Wrap the full stack so IDs are also attached to Starlette-generated 500 responses.
    app.middleware_stack = RequestIdMiddleware(app.build_middleware_stack())
    return app


app = create_app()
