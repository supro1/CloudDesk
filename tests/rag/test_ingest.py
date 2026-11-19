from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import create_database_engine, create_tables
from backend.app.repositories import SupportArticleRepository
from backend.app.schemas.common import TicketCategory
from backend.app.services.knowledge_service import KnowledgeService
from rag.embeddings import FakeEmbeddings
from rag.vector_store import InMemoryVectorStore


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    async with AsyncSession(engine, expire_on_commit=False) as test_session:
        yield test_session
    await engine.dispose()


async def test_ingest_persists_articles_and_builds_searchable_index(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    (tmp_path / "mfa-recovery.md").write_text(
        "---\n"
        "title: MFA recovery\n"
        "category: login_issue\n"
        "tags: [mfa, recovery]\n"
        "summary: Recover from authenticator lockout.\n"
        "---\n"
        "# Recovery\n"
        "Use the verified authenticator recovery process after an MFA lockout.\n",
        encoding="utf-8",
    )
    store = InMemoryVectorStore(dimensions=64)
    service = KnowledgeService(store, FakeEmbeddings(dimensions=64))

    result = await service.reindex(session, tmp_path)

    assert result.article_count == 1
    assert result.chunk_count == 1
    assert await SupportArticleRepository(session).count_published() == 1
    articles = await SupportArticleRepository(session).list_published()
    evidence = await service.search(
        articles,
        "authenticator MFA lockout",
        category=TicketCategory.LOGIN_ISSUE,
        mode="keyword",
    )

    assert len(evidence) == 1
    assert evidence[0].article_id == "mfa-recovery"
    assert evidence[0].source == "kb://mfa-recovery#recovery"
    assert await store.count() == 1
    await service.close()


async def test_reindex_is_idempotent_for_article_records(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    (tmp_path / "guide.md").write_text(
        "---\n"
        "title: Guide\n"
        "category: other\n"
        "tags: [guide]\n"
        "summary: A guide.\n"
        "---\n"
        "Content.\n",
        encoding="utf-8",
    )
    service = KnowledgeService(
        InMemoryVectorStore(dimensions=32),
        FakeEmbeddings(dimensions=32),
    )

    await service.reindex(session, tmp_path)
    await service.reindex(session, tmp_path)

    articles = await SupportArticleRepository(session).list_published()
    assert len(articles) == 1
    assert articles[0].slug == "guide"
    await service.close()


async def test_reindex_unpublishes_source_articles_removed_from_directory(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    article_path = tmp_path / "guide.md"
    article_path.write_text(
        "---\n"
        "title: Guide\n"
        "category: other\n"
        "tags: [guide]\n"
        "summary: A guide.\n"
        "---\n"
        "Content.\n",
        encoding="utf-8",
    )
    service = KnowledgeService(
        InMemoryVectorStore(dimensions=32),
        FakeEmbeddings(dimensions=32),
    )

    await service.reindex(session, tmp_path)
    article_path.unlink()
    result = await service.reindex(session, tmp_path)

    assert result.article_count == 0
    assert result.chunk_count == 0
    assert await SupportArticleRepository(session).count_published() == 0
    await service.close()
