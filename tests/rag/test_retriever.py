from collections.abc import Mapping, Sequence

import pytest

from rag.chunking import ArticleChunk
from rag.embeddings import FakeEmbeddings
from rag.retriever import Evidence, HybridRetriever
from rag.vector_store import VectorSearchResult


def _chunk(
    chunk_id: str,
    article_id: str,
    title: str,
    content: str,
    category: str = "billing",
) -> ArticleChunk:
    return ArticleChunk(
        id=chunk_id,
        page_content=content,
        metadata={
            "article_slug": article_id,
            "title": title,
            "category": category,
            "source": f"kb://{article_id}#section",
        },
    )


class _VectorStore:
    def __init__(self, results: Sequence[VectorSearchResult]) -> None:
        self.results = list(results)
        self.filters: Mapping[str, str] | None = None
        self.calls = 0

    async def search(
        self,
        query_embedding: Sequence[float],
        *,
        limit: int = 4,
        filters: Mapping[str, str] | None = None,
    ) -> list[VectorSearchResult]:
        self.calls += 1
        self.filters = filters
        return [
            result
            for result in self.results
            if filters is None
            or all(result.chunk.metadata.get(key) == value for key, value in filters.items())
        ][:limit]


@pytest.mark.asyncio
async def test_hybrid_retrieval_fuses_ranks_and_returns_cited_unique_articles() -> None:
    first_chunk = _chunk(
        "seat-count-1",
        "seat-count",
        "Seat count billing",
        "Billing invoice for the current seat count.",
    )
    duplicate_chunk = _chunk(
        "seat-count-2",
        "seat-count",
        "Seat count billing",
        "The invoice changes with seat count.",
    )
    refund_chunk = _chunk(
        "refunds",
        "refunds",
        "Refund policy",
        "Billing refunds and payment disputes.",
    )
    store = _VectorStore(
        [
            VectorSearchResult(refund_chunk, 0.9),
            VectorSearchResult(duplicate_chunk, 0.8),
        ]
    )
    retriever = HybridRetriever(
        [first_chunk, duplicate_chunk, refund_chunk],
        store,
        FakeEmbeddings(dimensions=16),
    )

    evidence = await retriever.retrieve("seat count", top_k=3)

    assert [item.article_id for item in evidence] == ["seat-count", "refunds"]
    assert len({item.article_id for item in evidence}) == len(evidence)
    assert evidence[0].source == "kb://seat-count#section"
    assert evidence[0].url == "/knowledge/seat-count"
    assert set(evidence[0].as_dict()) == {
        "id",
        "title",
        "source",
        "snippet",
        "score",
        "url",
        "article_id",
    }
    assert evidence[0].score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_keyword_mode_ranks_matching_articles_and_applies_category_filter() -> None:
    quota_chunk = _chunk(
        "quota",
        "storage-quota",
        "Storage quota",
        "Resolve storage quota exceeded errors.",
        "storage_quota",
    )
    billing_chunk = _chunk(
        "billing",
        "billing-seats",
        "Billing seats",
        "Review billed seat counts.",
        "billing",
    )
    store = _VectorStore([])
    retriever = HybridRetriever(
        [quota_chunk, billing_chunk],
        store,
        FakeEmbeddings(dimensions=16),
    )

    results = await retriever.retrieve(
        "quota exceeded",
        mode="keyword",
        category="storage_quota",
    )

    assert [item.article_id for item in results] == ["storage-quota"]
    assert store.calls == 0


@pytest.mark.asyncio
async def test_semantic_mode_uses_vector_results_without_keyword_candidates() -> None:
    semantic_chunk = _chunk(
        "semantic",
        "semantic-article",
        "Account access",
        "How to regain access to the workspace.",
        "login_issue",
    )
    irrelevant_keyword_chunk = _chunk(
        "keyword",
        "keyword-article",
        "Seat counts",
        "Billing seat counts.",
    )
    store = _VectorStore([VectorSearchResult(semantic_chunk, 0.8)])
    retriever = HybridRetriever(
        [semantic_chunk, irrelevant_keyword_chunk],
        store,
        FakeEmbeddings(dimensions=16),
    )

    results = await retriever.retrieve("workspace access", mode="semantic")

    assert [item.article_id for item in results] == ["semantic-article"]
    assert store.calls == 1


@pytest.mark.asyncio
async def test_reranker_reorders_evidence_and_invalid_order_is_reported() -> None:
    first = _chunk("first", "first", "First", "Searchable support content.")
    second = _chunk("second", "second", "Second", "Searchable support content.")
    store = _VectorStore(
        [VectorSearchResult(first, 0.9), VectorSearchResult(second, 0.8)]
    )

    async def reverse(query: str, evidence: Sequence[Evidence]) -> Sequence[str]:
        return [item.id for item in reversed(evidence)]

    retriever = HybridRetriever([first, second], store, reranker=reverse)
    results = await retriever.retrieve("searchable", mode="semantic")
    assert [item.id for item in results] == ["second", "first"]

    async def invalid(query: str, evidence: Sequence[Evidence]) -> Sequence[str]:
        return ["unknown"]

    retriever = HybridRetriever([first, second], store, reranker=invalid)
    with pytest.raises(ValueError, match="each evidence id exactly once"):
        await retriever.retrieve("searchable", mode="semantic")


@pytest.mark.asyncio
async def test_retriever_validates_options_and_skips_empty_queries() -> None:
    store = _VectorStore([])
    retriever = HybridRetriever([], store, FakeEmbeddings(dimensions=16))

    assert await retriever.retrieve("  ") == []
    with pytest.raises(ValueError, match="top_k"):
        await retriever.retrieve("query", top_k=0)
    with pytest.raises(ValueError, match="mode"):
        await retriever.retrieve("query", mode="invalid")
