from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol


class BillingIntegration(Protocol):
    async def create_refund_request(
        self,
        *,
        ticket_id: str,
        customer_id: str,
        amount: Decimal,
        reason: str,
    ) -> Mapping[str, object]: ...


class WorkspaceIntegration(Protocol):
    async def reset_setting(
        self,
        *,
        workspace_id: str,
        setting_name: str,
    ) -> Mapping[str, object]: ...


class ServiceStatusIntegration(Protocol):
    async def check_service_status(
        self, service_name: str
    ) -> Mapping[str, object]: ...
