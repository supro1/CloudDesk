from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import main
from backend.app.core.config import Settings
from backend.app.core.database import create_database_engine, create_tables
from backend.app.models.entities import (
    Customer,
    Incident,
    Profile,
    Subscription,
    Ticket,
    TicketMessage,
    Workspace,
)
from backend.app.repositories import (
    BaseRepository,
    TicketMessageRepository,
    TicketRepository,
)
from backend.app.schemas.common import TicketCategory
from backend.app.services.seed_service import bootstrap_demo_data


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    async with AsyncSession(engine, expire_on_commit=False) as test_session:
        yield test_session
    await engine.dispose()


@pytest.fixture
def sample_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "sample_data"


async def test_bootstrap_loads_demo_fixtures_with_relationships(
    session: AsyncSession, sample_data_dir: Path
) -> None:
    assert await bootstrap_demo_data(session, sample_data_dir)

    assert await BaseRepository(session, Profile).count() == 3
    assert await BaseRepository(session, Customer).count() == 8
    assert await BaseRepository(session, Subscription).count() == 8
    assert await BaseRepository(session, Workspace).count() == 9
    assert await BaseRepository(session, Ticket).count() == 13
    assert await BaseRepository(session, Incident).count() == 2
    assert await BaseRepository(session, TicketMessage).count() == 16

    refund_ticket = await TicketRepository(session).get_by_ticket_number("CD-1002")
    assert refund_ticket is not None
    assert refund_ticket.category is TicketCategory.BILLING
    assert refund_ticket.customer_id == "10000000-0000-4000-8000-000000000006"

    history_ticket = await TicketRepository(session).get_by_ticket_number("CD-1008")
    assert history_ticket is not None
    history = await TicketMessageRepository(session).list_for_ticket(history_ticket.id)
    resolution = next(message for message in history if message.is_internal)
    assert resolution.is_internal
    assert "Reconnect the integration" in resolution.body


async def test_bootstrap_is_idempotent(session: AsyncSession, sample_data_dir: Path) -> None:
    assert await bootstrap_demo_data(session, sample_data_dir)
    assert not await bootstrap_demo_data(session, sample_data_dir)

    assert await BaseRepository(session, Customer).count() == 8
    assert await BaseRepository(session, Ticket).count() == 13


async def test_bootstrap_skips_any_nonempty_database(
    session: AsyncSession, sample_data_dir: Path
) -> None:
    await BaseRepository(session, Profile).create(
        email="existing@example.test",
        display_name="Existing profile",
        role="viewer",
    )
    await session.commit()

    assert not await bootstrap_demo_data(session, sample_data_dir)
    assert await BaseRepository(session, Profile).count() == 1
    assert await BaseRepository(session, Customer).count() == 0


async def test_bootstrap_reports_missing_fixture_without_partial_writes(
    session: AsyncSession, tmp_path: Path
) -> None:
    with pytest.raises(FileNotFoundError):
        await bootstrap_demo_data(session, tmp_path)

    assert await BaseRepository(session, Customer).count() == 0
    assert await BaseRepository(session, Ticket).count() == 0


async def test_application_lifespan_bootstraps_only_in_demo_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, object]] = []

    class SessionContext:
        async def __aenter__(self) -> str:
            return "test-session"

        async def __aexit__(self, *_: object) -> None:
            return None

    async def create_tables_stub() -> None:
        calls.append(("create_tables", None))

    async def dispose_engine_stub() -> None:
        calls.append(("dispose_engine", None))

    async def bootstrap_stub(session: object, sample_data_dir: Path) -> bool:
        calls.append(("bootstrap", (session, sample_data_dir)))
        return True

    monkeypatch.setattr(main, "create_tables", create_tables_stub)
    monkeypatch.setattr(main, "dispose_engine", dispose_engine_stub)
    monkeypatch.setattr(main, "session_factory", SessionContext)
    monkeypatch.setattr(main, "bootstrap_demo_data", bootstrap_stub)

    for demo_mode in (False, True):
        app = main.create_app(
            Settings(_env_file=None, demo_mode=demo_mode, sample_data_dir=tmp_path)
        )
        async with app.router.lifespan_context(app):
            pass

    assert calls.count(("bootstrap", ("test-session", tmp_path))) == 1
    assert calls.count(("create_tables", None)) == 2
    assert calls.count(("dispose_engine", None)) == 2
