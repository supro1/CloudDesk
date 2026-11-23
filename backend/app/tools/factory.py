from __future__ import annotations

from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.config import Settings
from backend.app.services.knowledge_service import KnowledgeService
from backend.app.tools.policy import ToolPolicy
from backend.app.tools.read_only import create_read_only_tools
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.writes import create_write_tools
from integrations import SupportIntegrations, create_mock_integrations


def create_support_tools(
    session_factory: async_sessionmaker[AsyncSession],
    knowledge_service: KnowledgeService,
    integrations: SupportIntegrations | None = None,
) -> list[BaseTool]:
    integrations = integrations or create_mock_integrations()
    return [
        *create_read_only_tools(
            session_factory,
            knowledge_service,
            integrations.service_status,
        ),
        *create_write_tools(
            session_factory,
            integrations.billing,
            integrations.workspace,
        ),
    ]


def create_support_tool_registry(
    session_factory: async_sessionmaker[AsyncSession],
    knowledge_service: KnowledgeService,
    *,
    integrations: SupportIntegrations | None = None,
    settings: Settings | None = None,
) -> ToolRegistry:
    return ToolRegistry(
        create_support_tools(session_factory, knowledge_service, integrations),
        policy=ToolPolicy(settings),
        settings=settings,
    )
