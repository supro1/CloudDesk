from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import uuid4


@dataclass(slots=True)
class MockBillingIntegration:
    refund_requests: list[dict[str, object]] = field(default_factory=list)

    async def create_refund_request(
        self,
        *,
        ticket_id: str,
        customer_id: str,
        amount: Decimal,
        reason: str,
    ) -> dict[str, object]:
        request = {
            "request_id": str(uuid4()),
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "amount": str(amount),
            "reason": reason,
            "status": "request_created",
            "mock": True,
            "message": "A simulated refund request was created; no money was moved.",
        }
        self.refund_requests.append(request)
        return dict(request)


@dataclass(slots=True)
class MockWorkspaceIntegration:
    settings: dict[tuple[str, str], object] = field(default_factory=dict)
    defaults: dict[str, object] = field(
        default_factory=lambda: {
            "sso": True,
            "external_sharing": False,
            "mfa": True,
        }
    )

    async def reset_setting(
        self,
        *,
        workspace_id: str,
        setting_name: str,
    ) -> dict[str, object]:
        if setting_name not in self.defaults:
            raise ValueError(f"Unsupported demo setting: {setting_name}")
        value = self.defaults[setting_name]
        self.settings[(workspace_id, setting_name)] = value
        return {
            "workspace_id": workspace_id,
            "setting": setting_name,
            "value": value,
            "status": "reset",
            "mock": True,
        }


@dataclass(slots=True)
class MockServiceStatusIntegration:
    statuses: dict[str, str] = field(
        default_factory=lambda: {
            "api": "operational",
            "authentication": "operational",
            "billing": "operational",
            "storage": "operational",
        }
    )

    async def check_service_status(self, service_name: str) -> dict[str, object]:
        normalized_name = service_name.strip().lower()
        if not normalized_name:
            raise ValueError("service_name must not be empty")
        status = self.statuses.get(normalized_name)
        return {
            "service": normalized_name,
            "status": status or "unknown",
            "mock": True,
            "message": (
                "Status returned by the local mock."
                if status is not None
                else "No mock status is configured for this service."
            ),
        }
