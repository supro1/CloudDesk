from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import SupportArticle
from backend.app.repositories import SupportArticleRepository
from backend.app.schemas.common import TicketCategory
from rag.chunking import (
    ArticleChunk,
    KnowledgeArticle,
    chunk_article,
    load_article_files,
)
from rag.embeddings import FakeEmbeddings
from rag.retriever import Evidence, HybridRetriever, RetrievalMode
from rag.vector_store import VectorStoreService


@dataclass(frozen=True, slots=True)
class IngestResult:
    article_count: int
    chunk_count: int


class KnowledgeService:
    def __init__(
        self,
        vector_store: VectorStoreService,
        embeddings: FakeEmbeddings,
    ) -> None:
        self._vector_store = vector_store
        self._embeddings = embeddings
        self._indexed_signature: tuple[tuple[str, str, str, str], ...] | None = None
        self._chunks: list[ArticleChunk] = []
        self._index_lock = asyncio.Lock()

    async def reindex(
        self,
        session: AsyncSession,
        articles_directory: Path,
    ) -> IngestResult:
        source_articles = load_article_files(articles_directory)
        repository = SupportArticleRepository(session)

        for article in source_articles:
            values = {
                "title": article.title,
                "category": article.category,
                "tags": list(article.tags),
                "summary": article.summary,
                "content": article.content,
                "source_path": article.source_path.name,
                "is_published": True,
            }
            existing = await repository.get_by_slug(article.slug)
            if existing is None:
                await repository.create(slug=article.slug, **values)
            else:
                await repository.update(existing.id, values)

        source_filenames = {article.source_path.name for article in source_articles}
        for existing in await repository.list(limit=10_000):
            if (
                existing.is_published
                and existing.source_path is not None
                and Path(existing.source_path).name not in source_filenames
            ):
                await repository.update(existing.id, {"is_published": False})

        await session.flush()
        records = await repository.list_published(limit=10_000)
        chunks = [_chunk for record in records for _chunk in chunk_article(_to_article(record))]

        async with self._index_lock:
            await self._replace_index(chunks)
            await session.commit()
            self._indexed_signature = _signature(records)

        return IngestResult(article_count=len(records), chunk_count=len(chunks))

    async def search(
        self,
        articles: Sequence[SupportArticle],
        query: str,
        *,
        category: TicketCategory | None = None,
        mode: RetrievalMode = "hybrid",
        top_k: int = 3,
    ) -> list[Evidence]:
        signature = _signature(articles)
        async with self._index_lock:
            if signature != self._indexed_signature:
                chunks = [
                    chunk
                    for article in articles
                    for chunk in chunk_article(_to_article(article))
                ]
                await self._replace_index(chunks)
                self._indexed_signature = signature
                self._chunks = chunks
            chunks = self._chunks

        retriever = HybridRetriever(
            chunks,
            self._vector_store,
            self._embeddings,
        )
        return await retriever.retrieve(
            query,
            category=category.value if category is not None else None,
            mode=mode,
            top_k=top_k,
        )

    async def close(self) -> None:
        await self._vector_store.aclose()

    async def _replace_index(self, chunks: list[ArticleChunk]) -> None:
        self._indexed_signature = None
        await self._vector_store.clear()
        if chunks:
            vectors = self._embeddings.embed_documents(
                [chunk.page_content for chunk in chunks]
            )
            await self._vector_store.add_documents(chunks, vectors)
        self._chunks = chunks


def _to_article(record: SupportArticle) -> KnowledgeArticle:
    category = record.category
    return KnowledgeArticle(
        slug=record.slug,
        title=record.title,
        category=TicketCategory(category) if category is not None else None,
        tags=tuple(record.tags),
        summary=record.summary,
        content=record.content,
        source_path=Path(record.source_path or f"{record.slug}.md"),
    )


def _signature(
    articles: Sequence[SupportArticle],
) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        sorted(
            (
                article.id,
                article.slug,
                article.updated_at.isoformat(),
                article.content,
            )
            for article in articles
        )
    )
