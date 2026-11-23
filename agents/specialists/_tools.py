from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.tools.registry import ToolRegistry


async def execute_tool(
    registry: ToolRegistry,
    name: str,
    arguments: Mapping[str, Any],
) -> Any:
    result = await registry.execute(name, arguments)
    if not result.ok:
        raise RuntimeError(result.error or f"Tool {name!r} failed")
    return result.result


__all__ = ["execute_tool"]
