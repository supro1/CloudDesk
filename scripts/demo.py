from __future__ import annotations

import argparse
import sys
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from backend.app.core.config import get_settings
from backend.app.main import app


def _require_success(response: Response) -> dict[str, Any]:
    if not response.is_success:
        raise RuntimeError(
            f"Demo API request failed ({response.status_code}): {response.text}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError("Demo API returned an unexpected response")
    return payload


def run_demo(ticket_number: str) -> None:
    settings = get_settings()
    if not settings.demo_mode:
        raise RuntimeError("The demo script requires DEMO_MODE=true")
    if settings.effective_jwt_secret is None:
        raise RuntimeError("Set JWT_SECRET in .env before running the demo")

    with TestClient(app) as client:
        login = _require_success(
            client.post(
                "/api/v1/auth/login",
                json={"email": "sam.agent@clouddesk.demo"},
            )
        )
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        tickets_page = _require_success(
            client.get("/api/v1/tickets", headers=headers, params={"limit": 100})
        )
        ticket = next(
            (
                item
                for item in tickets_page["items"]
                if item["ticket_number"] == ticket_number
            ),
            None,
        )
        if ticket is None:
            raise RuntimeError(f"Demo ticket {ticket_number} was not found")

        ticket_id = ticket["id"]
        details = _require_success(
            client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
        )
        approval = details.get("approval")
        if not (
            details["status"] == "waiting_on_approval"
            and isinstance(approval, dict)
            and approval["status"] == "pending"
        ):
            _require_success(
                client.post(f"/api/v1/tickets/{ticket_id}/run", headers=headers)
            )

        workflow = _require_success(
            client.get(f"/api/v1/tickets/{ticket_id}/workflow", headers=headers)
        )
        print(
            f"{ticket_number}: category={workflow.get('category')} "
            f"severity={workflow.get('severity')} status={workflow['status']}"
        )

        if workflow["status"] == "paused":
            details = _require_success(
                client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
            )
            approval = details.get("approval")
            if not isinstance(approval, dict) or approval.get("status") != "pending":
                raise RuntimeError("Workflow paused without a pending approval request")
            print(f"Approval needed: {approval['summary']}")
            choice = input("Approve this mock action? [y/N] ").strip().casefold()
            approved = choice in {"y", "yes"}
            reason = input("Optional decision note: ").strip()
            path = "approve" if approved else "reject"
            result = _require_success(
                client.post(
                    f"/api/v1/approvals/{approval['id']}/{path}",
                    headers=headers,
                    json={"reason": reason or None},
                )
            )
            print(
                f"Decision={result['approval']['status']} "
                f"workflow={result['workflow_status']}"
            )
            if approved:
                print("The integration is a mock; no money was moved.")
        elif workflow["status"] != "completed":
            raise RuntimeError(
                f"Workflow ended in unexpected state {workflow['status']!r}"
            )

        if ticket_number == "CD-1005":
            escalations = _require_success(
                client.get(
                    "/api/v1/escalations",
                    headers=headers,
                    params={"ticket_id": ticket_id},
                )
            )
            for record in escalations["items"]:
                print(f"Escalated to {record['team']}: {record['reason']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a CloudDesk support workflow demo.")
    parser.add_argument(
        "--ticket",
        default="CD-1002",
        choices=("CD-1002", "CD-1005"),
        help="Demo ticket to process (default: CD-1002).",
    )
    args = parser.parse_args()
    run_demo(args.ticket)
    return 0


if __name__ == "__main__":
    sys.exit(main())
