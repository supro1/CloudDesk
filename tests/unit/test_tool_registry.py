import asyncio

import pytest
from langchain_core.tools import tool

from backend.app.core.config import Settings
from backend.app.tools.policy import ToolPolicy
from backend.app.tools.registry import ToolRegistry


def test_registry_executes_only_registered_tools_and_returns_results() -> None:
    @tool
    async def sample_read(value: str) -> str:
        """Return the input value."""
        return value

    registry = ToolRegistry(
        [sample_read],
        settings=Settings(_env_file=None),
    )

    result = asyncio.run(
        registry.execute("sample_read", {"value": "hello"}, approved=True)
    )

    assert registry.tool_names == ("sample_read",)
    assert result.ok
    assert result.result == "hello"
    assert result.error is None


def test_unknown_tool_is_rejected_even_when_approved() -> None:
    registry = ToolRegistry(settings=Settings(_env_file=None))

    result = asyncio.run(
        registry.execute("unknown_tool", {}, approved=True)
    )

    assert not result.ok
    assert result.requires_approval
    assert "not registered" in (result.error or "")


def test_registry_blocks_approval_gated_tool_before_invocation() -> None:
    calls: list[str] = []

    @tool
    async def reset_demo_setting(setting: str) -> str:
        """Change a demo workspace setting."""
        calls.append(setting)
        return "changed"

    registry = ToolRegistry(
        [reset_demo_setting],
        settings=Settings(_env_file=None),
    )

    result = asyncio.run(
        registry.execute("reset_demo_setting", {"setting": "sso"}, approved=False)
    )

    assert not result.ok
    assert result.requires_approval
    assert calls == []


def test_registry_accepts_explicit_approval_for_gated_tool() -> None:
    @tool
    async def reset_demo_setting(setting: str) -> str:
        """Change a demo workspace setting."""
        return f"changed {setting}"

    registry = ToolRegistry(
        [reset_demo_setting],
        settings=Settings(_env_file=None),
    )

    result = asyncio.run(
        registry.execute("reset_demo_setting", {"setting": "sso"}, approved=True)
    )

    assert result.ok
    assert result.result == "changed sso"
    assert not result.requires_approval


def test_registry_rejects_duplicate_tool_names() -> None:
    @tool
    async def sample_read(value: str) -> str:
        """Return the input value."""
        return value

    with pytest.raises(ValueError, match="duplicate tool name"):
        ToolRegistry([sample_read, sample_read], settings=Settings(_env_file=None))


def test_registry_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        ToolRegistry(timeout_seconds=0, settings=Settings(_env_file=None))


def test_registry_converts_timeout_to_explicit_failure() -> None:
    @tool
    async def slow_tool() -> str:
        """Wait longer than the registry timeout."""
        await asyncio.sleep(0.05)
        return "finished"

    registry = ToolRegistry(
        [slow_tool],
        timeout_seconds=0.001,
        settings=Settings(_env_file=None),
    )

    result = asyncio.run(registry.execute("slow_tool", {}, approved=True))

    assert not result.ok
    assert result.error_type == "TimeoutError"
    assert result.error == "Tool execution timed out."


def test_registry_converts_tool_exception_without_exposing_exception_text() -> None:
    @tool
    async def failing_tool() -> str:
        """Raise an internal failure."""
        raise RuntimeError("private diagnostic detail")

    registry = ToolRegistry(
        [failing_tool],
        settings=Settings(_env_file=None),
    )

    result = asyncio.run(registry.execute("failing_tool", {}, approved=True))

    assert not result.ok
    assert result.error_type == "RuntimeError"
    assert result.error == "Tool execution failed."
    assert "private diagnostic detail" not in result.error


def test_registry_applies_injected_policy_before_execution() -> None:
    @tool
    async def create_refund_request(amount: str) -> str:
        """Create a refund request."""
        return amount

    settings = Settings(
        _env_file=None,
        approval_required_for_refunds=False,
        max_refund_without_approval=10,
    )
    registry = ToolRegistry(
        [create_refund_request],
        policy=ToolPolicy(settings),
        settings=settings,
    )

    result = asyncio.run(
        registry.execute("create_refund_request", {"amount": "11"})
    )

    assert not result.ok
    assert result.requires_approval
