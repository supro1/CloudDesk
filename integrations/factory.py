from __future__ import annotations

from dataclasses import dataclass

from integrations.mock.services import (
    MockBillingIntegration,
    MockServiceStatusIntegration,
    MockWorkspaceIntegration,
)
from integrations.protocols import (
    BillingIntegration,
    ServiceStatusIntegration,
    WorkspaceIntegration,
)


@dataclass(frozen=True, slots=True)
class SupportIntegrations:
    billing: BillingIntegration
    workspace: WorkspaceIntegration
    service_status: ServiceStatusIntegration


def create_mock_integrations() -> SupportIntegrations:
    return SupportIntegrations(
        billing=MockBillingIntegration(),
        workspace=MockWorkspaceIntegration(),
        service_status=MockServiceStatusIntegration(),
    )
