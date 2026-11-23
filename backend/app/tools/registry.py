from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from langchain_core.tools import BaseTool

from backend.app.core.config import Settings, get_settings
from backend.app.core.observability import (
    elapsed_ms,
    record_tool_call,
    summarize_tool_result,
)
from backend.app.tools.policy import ToolPolicy

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool_name: str
    ok: bool
    result: Any = None
    error: str | None = None
    error_type: str | None = None
    requires_approval: bool = False


class ToolRegistry:
    """Allow-listed async tool execution with approval and timeout enforcement."""

    def __init__(
        self,
        tools: Iterable[BaseTool] = (),
        *,
        policy: ToolPolicy | None = None,
        timeout_seconds: float | None = None,
        settings: Settings | None = None,
    ) -> None:
        settings = settings or get_settings()
        timeout = (
            settings.tool_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        if timeout <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        self._policy = policy or ToolPolicy(settings)
        self._timeout_seconds = timeout
        self._tools: dict[str, BaseTool] = {}
        for tool in tools:
            if not isinstance(tool, BaseTool):
                raise TypeError("registered tools must be LangChain BaseTool instances")
            if not tool.name or not tool.name.strip():
                raise ValueError("registered tools must have a non-empty name")
            if tool.name in self._tools:
                raise ValueError(f"duplicate tool name: {tool.name}")
            self._tools[tool.name] = tool

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    async def execute(
        self,
        name: str,
        arguments: Mapping[str, Any],
        *,
        approved: bool = False,
    ) -> ToolResult:
        started_at = perf_counter()
        result = await self._execute(name, arguments, approved=approved)
        await record_tool_call(
            tool_name=name,
            ok=result.ok,
            error_type=result.error_type,
            requires_approval=result.requires_approval,
            result_summary=(
                summarize_tool_result(name, result.result) if result.ok else None
            ),
            duration_ms=elapsed_ms(started_at),
        )
        return result

    async def _execute(
        self,
        name: str,
        arguments: Mapping[str, Any],
        *,
        approved: bool,
    ) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            decision = self._policy.evaluate(name, arguments)
            return ToolResult(
                tool_name=name,
                ok=False,
                error="Tool is not registered and cannot be executed.",
                requires_approval=decision.approval_required,
            )

        if not isinstance(arguments, Mapping):
            return ToolResult(
                tool_name=name,
                ok=False,
                error="Tool arguments must be a mapping.",
                error_type="InvalidArguments",
            )

        decision = self._policy.evaluate(name, arguments)
        if decision.approval_required and not approved:
            return ToolResult(
                tool_name=name,
                ok=False,
                error=decision.reason or "Human approval is required.",
                requires_approval=True,
            )

        try:
            result = await asyncio.wait_for(
                tool.ainvoke(dict(arguments)),
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            logger.warning(
                "Tool %s timed out after %s seconds",
                name,
                self._timeout_seconds,
            )
            return ToolResult(
                tool_name=name,
                ok=False,
                error="Tool execution timed out.",
                error_type="TimeoutError",
            )
        # Tool implementations are an extension boundary and may raise different exception types.
        except Exception as error:  # noqa: BLE001
            logger.error("Tool %s failed with %s", name, type(error).__name__)
            return ToolResult(
                tool_name=name,
                ok=False,
                error="Tool execution failed.",
                error_type=type(error).__name__,
            )

        return ToolResult(tool_name=name, ok=True, result=result)
