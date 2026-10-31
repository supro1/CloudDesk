from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import (
    ApprovalRequest,
    AuditLog,
    Customer,
    CustomerMemory,
    Escalation,
    Incident,
    Product,
    Profile,
    ResolutionAction,
    Subscription,
    SupportArticle,
    Ticket,
    TicketMessage,
    WorkflowEvent,
    WorkflowRun,
    Workspace,
)
from backend.app.repositories import (
    BaseRepository,
    CustomerRepository,
    IncidentRepository,
    ProductRepository,
    ProfileRepository,
    SubscriptionRepository,
    TicketMessageRepository,
    TicketRepository,
    WorkspaceRepository,
)
from backend.app.schemas.common import TicketCategory

_DATABASE_MODELS = (
    Profile,
    Customer,
    Subscription,
    Workspace,
    Product,
    Ticket,
    TicketMessage,
    SupportArticle,
    Incident,
    WorkflowRun,
    WorkflowEvent,
    ResolutionAction,
    ApprovalRequest,
    Escalation,
    CustomerMemory,
    AuditLog,
)
_DATA_FILES = (
    "profiles.json",
    "customers.json",
    "subscriptions.json",
    "workspaces.json",
    "products.json",
    "tickets.json",
    "incidents.json",
    "previous_resolutions.json",
)


def _load_records(data_dir: Path, filename: str) -> list[dict[str, Any]]:
    path = data_dir / filename
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise ValueError(f"{path} must contain a JSON array of objects")
    return records


def _required_reference(
    index: dict[str, Any], key: str, reference: str, *, filename: str
) -> Any:
    try:
        return index[reference]
    except KeyError as error:
        raise ValueError(f"{filename} references unknown {key}: {reference}") from error


async def _is_database_empty(session: AsyncSession) -> bool:
    for model in _DATABASE_MODELS:
        if await BaseRepository(session, model).count():
            return False
    return True


async def bootstrap_demo_data(
    session: AsyncSession, sample_data_dir: Path = Path("sample_data")
) -> bool:
    """Load the demo fixtures once, atomically, into an empty database."""
    async with session.begin():
        if not await _is_database_empty(session):
            return False

        datasets = {
            filename: _load_records(sample_data_dir, filename) for filename in _DATA_FILES
        }

        profiles = ProfileRepository(session)
        customers = CustomerRepository(session)
        subscriptions = SubscriptionRepository(session)
        workspaces = WorkspaceRepository(session)
        products = ProductRepository(session)
        tickets = TicketRepository(session)
        messages = TicketMessageRepository(session)
        incidents = IncidentRepository(session)

        for record in datasets["profiles.json"]:
            await profiles.create(**record)

        customer_by_email: dict[str, Customer] = {}
        for record in datasets["customers.json"]:
            customer = await customers.create(**record)
            customer_by_email[customer.email] = customer

        for record in datasets["subscriptions.json"]:
            values = dict(record)
            customer_email = values.pop("customer_email")
            customer = _required_reference(
                customer_by_email,
                "customer email",
                customer_email,
                filename="subscriptions.json",
            )
            await subscriptions.create(customer_id=customer.id, **values)

        for record in datasets["workspaces.json"]:
            values = dict(record)
            customer_email = values.pop("customer_email")
            customer = _required_reference(
                customer_by_email,
                "customer email",
                customer_email,
                filename="workspaces.json",
            )
            await workspaces.create(customer_id=customer.id, **values)

        for record in datasets["products.json"]:
            await products.create(**record)

        resolution_by_ticket: dict[str, dict[str, Any]] = {}
        for resolution in datasets["previous_resolutions.json"]:
            ticket_number = resolution["ticket_number"]
            if ticket_number in resolution_by_ticket:
                raise ValueError(f"previous_resolutions.json repeats ticket {ticket_number}")
            resolution_by_ticket[ticket_number] = resolution

        ticket_by_number: dict[str, Ticket] = {}
        for record in datasets["tickets.json"]:
            values = dict(record)
            customer_email = values.pop("customer_email")
            ticket_messages = values.pop("messages", [])
            customer = _required_reference(
                customer_by_email,
                "customer email",
                customer_email,
                filename="tickets.json",
            )
            category = values.get("category")
            if category is not None:
                values["category"] = TicketCategory(category)
            ticket = await tickets.create(customer_id=customer.id, **values)
            ticket_by_number[ticket.ticket_number] = ticket

            for message in ticket_messages:
                await messages.create(ticket_id=ticket.id, **message)

        for ticket_number, resolution in resolution_by_ticket.items():
            ticket = _required_reference(
                ticket_by_number,
                "ticket number",
                ticket_number,
                filename="previous_resolutions.json",
            )
            steps = "\n".join(
                f"{number}. {step}"
                for number, step in enumerate(resolution["steps"], start=1)
            )
            body = f"Resolution: {resolution['resolution']}\n\nSteps:\n{steps}"
            await messages.create(
                ticket_id=ticket.id,
                sender_type="agent",
                sender_name="CloudDesk Support",
                body=body,
                is_internal=True,
            )

        for record in datasets["incidents.json"]:
            await incidents.create(**record)

    return True
