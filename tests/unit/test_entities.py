from sqlalchemy import DateTime, JSON, String, create_engine, inspect, select
from sqlalchemy.orm import Session

from backend.app.models.entities import (
    Base,
    Customer,
    SupportArticle,
    Ticket,
    WorkflowRun,
)
from backend.app.schemas.common import TicketCategory


EXPECTED_CATEGORIES = {
    "login_issue",
    "billing",
    "api_failure",
    "workspace_permissions",
    "storage_quota",
    "integration",
    "feature_request",
    "account",
    "security",
    "other",
}

EXPECTED_TABLES = {
    "profiles",
    "customers",
    "subscriptions",
    "workspaces",
    "products",
    "tickets",
    "ticket_messages",
    "support_articles",
    "incidents",
    "workflow_runs",
    "workflow_events",
    "resolution_actions",
    "approval_requests",
    "escalations",
    "customer_memory",
    "audit_logs",
}


def test_ticket_category_values_match_the_product_contract() -> None:
    assert {category.value for category in TicketCategory} == EXPECTED_CATEGORIES


def test_all_entities_create_portable_sqlite_tables() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    assert isinstance(WorkflowRun.__table__.c.state.type, JSON)


def test_entities_use_portable_ids_timestamps_and_json_columns() -> None:
    for table in Base.metadata.tables.values():
        assert isinstance(table.c.id.type, String)
        assert table.c.id.type.length == 36
        assert isinstance(table.c.created_at.type, DateTime)
        assert isinstance(table.c.updated_at.type, DateTime)
        assert all(
            type(column.type) is JSON
            for column in table.columns
            if isinstance(column.type, JSON)
        )


def test_category_enum_round_trips_as_string_values() -> None:
    assert set(Ticket.__table__.c.category.type.enums) == EXPECTED_CATEGORIES

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        customer = Customer(name="Ada", email="ada@example.test")
        session.add(customer)
        session.flush()
        ticket = Ticket(
            ticket_number="CD-1001",
            customer_id=customer.id,
            subject="Cannot log in",
            channel="email",
            category=TicketCategory.LOGIN_ISSUE,
        )
        session.add(ticket)
        session.commit()

        persisted_ticket = session.scalar(
            select(Ticket).where(Ticket.ticket_number == "CD-1001")
        )

    assert persisted_ticket is not None
    assert persisted_ticket.category is TicketCategory.LOGIN_ISSUE
    assert persisted_ticket.id


def test_support_article_metadata_uses_portable_json() -> None:
    assert isinstance(SupportArticle.__table__.c.tags.type, JSON)
