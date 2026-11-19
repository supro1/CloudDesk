from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.core.config import Settings, get_settings

_NO_APPROVAL_TOOLS = frozenset(
    {
        "get_customer",
        "get_subscription",
        "get_ticket_history",
        "search_docs",
        "check_service_status",
        "update_ticket",
        "create_escalation",
    }
)


@dataclass(frozen=True, slots=True)
class ToolPolicyDecision:
    approval_required: bool
    reason: str | None = None


class ToolPolicy:
    """Apply deterministic approval rules before a registered tool can run."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def requires_approval(
        self,
        tool_name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> bool:
        return self.evaluate(tool_name, arguments).approval_required

    def evaluate(
        self,
        tool_name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> ToolPolicyDecision:
        if tool_name in _NO_APPROVAL_TOOLS:
            return ToolPolicyDecision(approval_required=False)

        if tool_name == "reset_demo_setting":
            return ToolPolicyDecision(
                approval_required=True,
                reason="Changing a workspace setting requires human approval.",
            )

        if tool_name == "create_refund_request":
            return self._refund_decision(arguments or {})

        return ToolPolicyDecision(
            approval_required=True,
            reason="Unclassified tools require human approval.",
        )

    def _refund_decision(
        self,
        arguments: Mapping[str, Any],
    ) -> ToolPolicyDecision:
        if self._settings.approval_required_for_refunds:
            return ToolPolicyDecision(
                approval_required=True,
                reason="Refund requests require human approval.",
            )

        amount = _refund_amount(arguments.get("amount"))
        if amount is None:
            return ToolPolicyDecision(
                approval_required=True,
                reason="A valid refund amount is required before policy can waive approval.",
            )

        maximum = self._settings.max_refund_without_approval
        if amount > maximum:
            return ToolPolicyDecision(
                approval_required=True,
                reason="The refund amount exceeds the configured approval-free limit.",
            )

        return ToolPolicyDecision(approval_required=False)


def _refund_amount(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount
