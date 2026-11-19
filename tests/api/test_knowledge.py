from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.config import Settings
from backend.app.core.database import create_database_engine, create_tables, get_session
from backend.app.main import create_app
from backend.app.models.entities import Profile, SupportArticle
from backend.app.schemas.common import TicketCategory

ADMIN_ID = "00000000-0000-4000-8000-000000000001"
VIEWER_ID = "00000000-0000-4000-8000-000000000003"


@pytest.fixture
async def knowledge_client() -> AsyncIterator[
    tuple[TestClient, async_sessionmaker[AsyncSession]]
]:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add_all(
            [
                Profile(
                    id=ADMIN_ID,
                    email="admin@clouddesk.demo",
                    display_name="CloudDesk Admin",
                    role="admin",
                    is_active=True,
                ),
                Profile(
                    id=VIEWER_ID,
                    email="vic.viewer@clouddesk.demo",
                    display_name="Vic Chen",
                    role="viewer",
                    is_active=True,
                ),
                SupportArticle(
                    slug="unpublished-guide",
                    title="Unpublished guide",
                    category=TicketCategory.OTHER,
                    content="This article is not published.",
                    is_published=False,
                ),
            ]
        )
        await session.commit()

    app = create_app(
        Settings(
            _env_file=None,
            demo_mode=True,
            jwt_secret="test-jwt-secret-with-at-least-32-bytes",
        )
    )

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client, session_maker
    await engine.dispose()


def _headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_knowledge_endpoints_enforce_roles_and_return_cited_search_results(
    knowledge_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = knowledge_client
    admin_headers = _headers(client, "admin@clouddesk.demo")
    viewer_headers = _headers(client, "vic.viewer@clouddesk.demo")

    assert client.get("/api/v1/knowledge").status_code == 401
    assert client.post(
        "/api/v1/knowledge/reindex",
        headers=viewer_headers,
    ).status_code == 403

    reindex = client.post("/api/v1/knowledge/reindex", headers=admin_headers)
    assert reindex.status_code == 200, reindex.text
    assert reindex.json()["article_count"] == 15
    assert reindex.json()["chunk_count"] > 15

    listing = client.get("/api/v1/knowledge?limit=1", headers=viewer_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 15
    article_slug = listing.json()["items"][0]["slug"]

    article = client.get(f"/api/v1/knowledge/{article_slug}", headers=viewer_headers)
    assert article.status_code == 200
    assert article.json()["slug"] == article_slug
    assert article.json()["content"]

    search = client.post(
        "/api/v1/knowledge/search",
        headers=viewer_headers,
        json={
            "query": "authenticator MFA lockout",
            "category": "login_issue",
            "mode": "keyword",
            "top_k": 2,
        },
    )
    assert search.status_code == 200, search.text
    evidence = search.json()["items"]
    assert evidence
    assert evidence[0]["article_id"] == "mfa-account-recovery"
    assert evidence[0]["source"].startswith("kb://mfa-account-recovery#")
    assert evidence[0]["url"] == "/knowledge/mfa-account-recovery"

    invalid_search = client.post(
        "/api/v1/knowledge/search",
        headers=viewer_headers,
        json={"query": "   "},
    )
    assert invalid_search.status_code == 422


def test_knowledge_detail_returns_not_found_for_unknown_or_unpublished_article(
    knowledge_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = knowledge_client
    headers = _headers(client, "vic.viewer@clouddesk.demo")
    for article_id in ("missing", "unpublished-guide"):
        response = client.get(f"/api/v1/knowledge/{article_id}", headers=headers)
        assert response.status_code == 404
