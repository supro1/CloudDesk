from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.schemas.common import TicketCategory
from rag.chunking import KnowledgeArticle, chunk_article, load_article_files


def test_loads_all_knowledge_articles_with_valid_categories() -> None:
    articles = load_article_files()

    assert len(articles) == 15
    assert all(isinstance(article.category, TicketCategory) for article in articles)
    assert all(article.title and article.summary and article.tags for article in articles)


def test_loader_rejects_invalid_front_matter(tmp_path: Path) -> None:
    (tmp_path / "invalid.md").write_text(
        "---\ntitle: Missing category\nsummary: Test\ncategory: unknown\ntags: [test]\n"
        "---\nBody",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown category"):
        load_article_files(tmp_path)


def test_chunk_article_splits_headings_and_keeps_citation_metadata() -> None:
    article = KnowledgeArticle(
        slug="login-help",
        title="Login help",
        category=TicketCategory.LOGIN_ISSUE,
        tags=("login",),
        summary="Troubleshoot login problems.",
        content="# SSO\nCheck identity provider.\n\n## MFA\nConfirm the user has a device.",
        source_path=Path("login-help.md"),
    )

    chunks = chunk_article(article)

    assert [chunk.metadata["heading"] for chunk in chunks] == ["SSO", "MFA"]
    assert [chunk.metadata["source"] for chunk in chunks] == [
        "kb://login-help#sso",
        "kb://login-help#mfa",
    ]
    assert chunks[0].page_content.startswith("Login help - SSO\n")
    assert chunks[0].metadata["category"] == "login_issue"


def test_chunk_article_windows_overlap_by_requested_characters() -> None:
    article = KnowledgeArticle(
        slug="long-guide",
        title="Long guide",
        category=TicketCategory.OTHER,
        tags=("guide",),
        summary="A long guide.",
        content="a" * 897 + " " * 3 + "b" * 1600,
        source_path=Path("long-guide.md"),
    )

    chunks = chunk_article(article, chunk_size=900, overlap=150)
    bodies = [chunk.page_content.split("\n", maxsplit=1)[1] for chunk in chunks]

    assert [len(body) for body in bodies] == [900, 900, 900, 250]
    assert bodies[0][-150:] == bodies[1][:150]
    assert bodies[1][-150:] == bodies[2][:150]


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (10, -1), (10, 10)],
)
def test_chunk_article_rejects_invalid_window_options(
    chunk_size: int, overlap: int
) -> None:
    article = KnowledgeArticle(
        slug="guide",
        title="Guide",
        category=TicketCategory.OTHER,
        tags=("guide",),
        summary="A guide.",
        content="Some content.",
        source_path=Path("guide.md"),
    )

    with pytest.raises(ValueError):
        chunk_article(article, chunk_size=chunk_size, overlap=overlap)
