from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel

from agents.prompts import SECURITY_PREAMBLE, TROUBLESHOOTING_PROMPT, wrap_untrusted
from agents.specialists._tools import execute_tool
from backend.app.core.llm import FakeLLM, call_structured
from backend.app.schemas.common import TicketCategory
from backend.app.schemas.workflow import (
    Diagnosis,
    DiagnosisDraft,
    DiagnosisStep,
    Evidence,
)
from backend.app.tools.registry import ToolRegistry

_SERVICE_BY_CATEGORY: dict[TicketCategory, str] = {
    TicketCategory.LOGIN_ISSUE: "authentication",
    TicketCategory.BILLING: "billing",
    TicketCategory.API_FAILURE: "api",
    TicketCategory.STORAGE_QUOTA: "storage",
    TicketCategory.INTEGRATION: "api",
}
_PLAYBOOKS: dict[TicketCategory, tuple[str, ...]] = {
    TicketCategory.LOGIN_ISSUE: (
        "Confirm the affected user and identity-provider configuration.",
        "Check whether the sign-in failure affects one user or the whole workspace.",
    ),
    TicketCategory.BILLING: (
        "Compare the invoice line items with the active subscription and usage.",
        "Do not promise or issue a refund before the required human review.",
    ),
    TicketCategory.API_FAILURE: (
        "Check the response code, request rate, and retry interval.",
        "Compare the integration's request pattern with the published API limits.",
    ),
    TicketCategory.STORAGE_QUOTA: (
        "Compare storage usage with the plan limit before recommending cleanup.",
        "Do not delete customer files as a troubleshooting shortcut.",
    ),
    TicketCategory.WORKSPACE_PERMISSIONS: (
        "Verify the workspace sharing policy and the user's role.",
        "Confirm whether the restriction affects one folder or the entire workspace.",
    ),
    TicketCategory.INTEGRATION: (
        "Confirm that the connected application is authorized.",
        "Test the integration with a non-sensitive event after reauthorization.",
    ),
    TicketCategory.FEATURE_REQUEST: (
        "Confirm the requested behavior and record it as product feedback.",
    ),
    TicketCategory.ACCOUNT: (
        "Verify account ownership and follow the approved account-change process.",
    ),
    TicketCategory.SECURITY: (
        "Preserve relevant evidence and route suspected compromise to security staff.",
    ),
    TicketCategory.OTHER: (
        "Confirm the affected account, expected behavior, and steps to reproduce.",
    ),
}


class TroubleshootingAgent:
    """Combine structured diagnosis with safe category-specific playbook steps."""

    def __init__(
        self,
        tools: ToolRegistry,
        llm: FakeLLM | BaseChatModel | None = None,
    ) -> None:
        self.tools = tools
        self.llm = llm

    async def run(
        self,
        issue_text: str,
        category: TicketCategory,
        evidence: Sequence[Evidence],
    ) -> Diagnosis:
        if not issue_text.strip():
            raise ValueError("issue_text must not be empty")
        service_name = _SERVICE_BY_CATEGORY.get(category)
        service_status: dict[str, Any] | None = None
        if service_name is not None:
            raw_status = await execute_tool(
                self.tools,
                "check_service_status",
                {"service_name": service_name},
            )
            if not isinstance(raw_status, dict):
                raise TypeError("check_service_status must return an object")
            service_status = raw_status

        evidence_prompt = "\n".join(
            f"- {item.title}: {wrap_untrusted(item.snippet)}" for item in evidence
        )
        response = await call_structured(
            DiagnosisDraft,
            system_prompt=f"{SECURITY_PREAMBLE}\n{TROUBLESHOOTING_PROMPT}",
            user_prompt=(
                f"Category: {category.value}\n"
                f"Issue:\n{wrap_untrusted(issue_text)}\n"
                f"Service status: {wrap_untrusted(str(service_status or 'not checked'))}\n"
                f"Support evidence:\n{evidence_prompt or 'No article evidence was found.'}"
            ),
            llm=self.llm,
        )
        causes = _unique_text(response.output.probable_causes)[:5]
        instructions = _unique_text(
            [*response.output.steps, *_PLAYBOOKS[category]]
        )[:8]
        return Diagnosis(
            probable_causes=causes,
            steps=[
                DiagnosisStep(number=index, instruction=instruction)
                for index, instruction in enumerate(instructions, start=1)
            ],
            service_status=service_status,
        )


def _unique_text(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            result.append(normalized)
            seen.add(key)
    return result


__all__ = ["TroubleshootingAgent"]
