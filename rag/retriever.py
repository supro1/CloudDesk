from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from rank_bm25 import BM25Okapi

from rag.chunking import ArticleChunk
from rag.embeddings import FakeEmbeddings
from rag.vector_store import VectorSearchResult, VectorStoreService

RetrievalMode = Literal["hybrid", "semantic", "keyword"]
_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
_RRF_K = 60
_SNIPPET_LENGTH = 500
_CANDIDATE_MULTIPLIER = 4


class QueryEmbedder(Protocol):
    def embed_query(self, text: str) -> Sequence[float]: ...


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    title: str
    source: str
    snippet: str
    score: float
    url: str
    article_id: str

    def as_dict(self) -> dict[str, str | float]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "snippet": self.snippet,
            "score": self.score,
            "url": self.url,
            "article_id": self.article_id,
        }


Reranker = Callable[[str, Sequence[Evidence]], Awaitable[Sequence[str]]]


class HybridRetriever:
    """Search indexed chunks semantically, by BM25, or with reciprocal-rank fusion."""

    def __init__(
        self,
        chunks: Sequence[ArticleChunk],
        vector_store: VectorStoreService,
        embeddings: QueryEmbedder | None = None,
        *,
        reranker: Reranker | None = None,
    ) -> None:
        self._chunks = tuple(chunks)
        self._vector_store = vector_store
        self._embeddings = embeddings or FakeEmbeddings()
        self._reranker = reranker

        keyword_entries = [
            (chunk, _tokenize(chunk.page_content))
            for chunk in self._chunks
        ]
        self._keyword_chunks = tuple(
            chunk for chunk, tokens in keyword_entries if tokens
        )
        self._bm25 = (
            BM25Okapi([tokens for _, tokens in keyword_entries if tokens])
            if self._keyword_chunks
            else None
        )

    async def retrieve(
        self,
        query: str,
        *,
        category: str | None = None,
        mode: RetrievalMode = "hybrid",
        top_k: int = 3,
    ) -> list[Evidence]:
        if mode not in {"hybrid", "semantic", "keyword"}:
            raise ValueError(f"unsupported retrieval mode: {mode}")
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        query_tokens = _tokenize(query)
        if not query_tokens or not self._chunks:
            return []

        filters = {"category": category} if category is not None else None
        candidate_limit = min(
            len(self._chunks),
            max(top_k, top_k * _CANDIDATE_MULTIPLIER),
        )
        semantic_results: list[VectorSearchResult] = []
        keyword_results: list[ArticleChunk] = []

        if mode in {"hybrid", "semantic"}:
            semantic_results = await self._vector_store.search(
                self._embeddings.embed_query(query),
                limit=candidate_limit,
                filters=filters,
            )
        if mode in {"hybrid", "keyword"}:
            keyword_results = self._keyword_search(query_tokens, category, candidate_limit)

        ranked_chunks = self._rank(semantic_results, keyword_results, query_tokens, category)
        evidence = [_to_evidence(chunk, score) for chunk, score in ranked_chunks]
        if self._reranker is not None and evidence:
            order = await self._reranker(query, evidence)
            evidence = _apply_reranker_order(evidence, order)
        return evidence[:top_k]

    def _keyword_search(
        self,
        query_tokens: Sequence[str],
        category: str | None,
        limit: int,
    ) -> list[ArticleChunk]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(query_tokens)
        matching = [
            (self._keyword_chunks[index], float(score))
            for index, score in enumerate(scores)
            if _matches_category(self._keyword_chunks[index], category)
            and _contains_query_term(self._keyword_chunks[index], query_tokens)
        ]
        matching.sort(key=lambda result: result[1], reverse=True)
        return [chunk for chunk, _ in matching[:limit]]

    def _rank(
        self,
        semantic_results: Sequence[VectorSearchResult],
        keyword_results: Sequence[ArticleChunk],
        query_tokens: Sequence[str],
        category: str | None,
    ) -> list[tuple[ArticleChunk, float]]:
        chunks_by_id: dict[str, ArticleChunk] = {}
        scores: dict[str, float] = {}

        for rank, result in enumerate(semantic_results, start=1):
            chunks_by_id[result.chunk.id] = result.chunk
            scores[result.chunk.id] = scores.get(result.chunk.id, 0.0) + 1 / (
                _RRF_K + rank
            )
        for rank, chunk in enumerate(keyword_results, start=1):
            chunks_by_id[chunk.id] = chunk
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1 / (_RRF_K + rank)

        query_set = set(query_tokens)
        ranked: list[tuple[ArticleChunk, float]] = []
        for chunk_id, chunk in chunks_by_id.items():
            if not _matches_category(chunk, category):
                continue
            title_tokens = set(_tokenize(str(chunk.metadata.get("title", ""))))
            title_overlap = len(query_set & title_tokens) / len(query_set)
            category_match = category is not None and chunk.metadata.get("category") == category
            heuristic_score = (0.01 if category_match else 0.0) + 0.01 * title_overlap
            ranked.append((chunk, scores[chunk_id] + heuristic_score))

        ranked.sort(key=lambda result: result[1], reverse=True)
        unique_articles: list[tuple[ArticleChunk, float]] = []
        seen_articles: set[str] = set()
        for chunk, score in ranked:
            article_id = _article_id(chunk)
            if article_id not in seen_articles:
                unique_articles.append((chunk, score))
                seen_articles.add(article_id)

        if unique_articles:
            max_score = unique_articles[0][1]
            unique_articles = [
                (chunk, score / max_score if max_score else 0.0)
                for chunk, score in unique_articles
            ]
        return unique_articles


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.casefold())


def _matches_category(chunk: ArticleChunk, category: str | None) -> bool:
    return category is None or chunk.metadata.get("category") == category


def _contains_query_term(chunk: ArticleChunk, query_tokens: Sequence[str]) -> bool:
    document_tokens = set(_tokenize(chunk.page_content))
    return any(token in document_tokens for token in query_tokens)


def _article_id(chunk: ArticleChunk) -> str:
    article_id = chunk.metadata.get("article_slug")
    return article_id if isinstance(article_id, str) and article_id else chunk.id


def _to_evidence(chunk: ArticleChunk, score: float) -> Evidence:
    article_id = _article_id(chunk)
    title = str(chunk.metadata.get("title", article_id))
    source = str(chunk.metadata.get("source", f"kb://{article_id}#section"))
    return Evidence(
        id=chunk.id,
        title=title,
        source=source,
        snippet=chunk.page_content[:_SNIPPET_LENGTH],
        score=score,
        url=f"/knowledge/{article_id}",
        article_id=article_id,
    )


def _apply_reranker_order(
    evidence: Sequence[Evidence],
    order: Sequence[str],
) -> list[Evidence]:
    evidence_by_id = {item.id: item for item in evidence}
    if len(order) != len(evidence_by_id) or set(order) != set(evidence_by_id):
        raise ValueError("reranker must return each evidence id exactly once")
    return [evidence_by_id[chunk_id] for chunk_id in order]
