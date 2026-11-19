from __future__ import annotations

import asyncio
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import AsyncQdrantClient, models

from backend.app.core.config import Settings, get_settings
from rag.chunking import ArticleChunk


@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    chunk: ArticleChunk
    score: float


class VectorStoreService(Protocol):
    async def add_documents(
        self,
        documents: Sequence[ArticleChunk],
        embeddings: Sequence[Sequence[float]],
    ) -> None: ...

    async def search(
        self,
        query_embedding: Sequence[float],
        *,
        limit: int = 4,
        filters: Mapping[str, str] | None = None,
    ) -> list[VectorSearchResult]: ...

    async def delete(self, ids: Sequence[str]) -> None: ...

    async def clear(self) -> None: ...

    async def count(self) -> int: ...

    async def health(self) -> bool: ...

    async def aclose(self) -> None: ...


class InMemoryVectorStore:
    def __init__(self, dimensions: int = 384) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than zero")
        self.dimensions = dimensions
        self._documents: dict[str, tuple[ArticleChunk, list[float]]] = {}
        self._lock = asyncio.Lock()

    async def add_documents(
        self,
        documents: Sequence[ArticleChunk],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        if len(documents) != len(embeddings):
            raise ValueError("documents and embeddings must have the same length")

        prepared = [
            (_copy_chunk(document), _validated_vector(embedding, self.dimensions))
            for document, embedding in zip(documents, embeddings, strict=True)
        ]
        async with self._lock:
            for document, embedding in prepared:
                self._documents[document.id] = (document, embedding)

    async def search(
        self,
        query_embedding: Sequence[float],
        *,
        limit: int = 4,
        filters: Mapping[str, str] | None = None,
    ) -> list[VectorSearchResult]:
        query = _validated_vector(query_embedding, self.dimensions)
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        async with self._lock:
            matches = [
                VectorSearchResult(_copy_chunk(document), _cosine_similarity(query, vector))
                for document, vector in self._documents.values()
                if _matches_filters(document, filters)
            ]
        matches.sort(key=lambda result: result.score, reverse=True)
        return matches[:limit]

    async def delete(self, ids: Sequence[str]) -> None:
        async with self._lock:
            for document_id in ids:
                self._documents.pop(document_id, None)

    async def clear(self) -> None:
        async with self._lock:
            self._documents.clear()

    async def count(self) -> int:
        async with self._lock:
            return len(self._documents)

    async def health(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None


class QdrantVectorStore:
    def __init__(
        self,
        client: AsyncQdrantClient,
        collection_name: str,
        dimensions: int = 384,
    ) -> None:
        if not collection_name.strip():
            raise ValueError("collection_name must not be empty")
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than zero")
        self.client = client
        self.collection_name = collection_name
        self.dimensions = dimensions
        self._initialized = False
        self._initialization_lock = asyncio.Lock()

    async def initialize(self) -> None:
        async with self._initialization_lock:
            if self._initialized:
                return
            if not await self.client.collection_exists(self.collection_name):
                await self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.dimensions,
                        distance=models.Distance.COSINE,
                    ),
                )
            self._initialized = True

    async def add_documents(
        self,
        documents: Sequence[ArticleChunk],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        if len(documents) != len(embeddings):
            raise ValueError("documents and embeddings must have the same length")
        if not documents:
            return

        await self.initialize()
        points = [
            models.PointStruct(
                id=_qdrant_id(document.id),
                vector=_validated_vector(embedding, self.dimensions),
                payload={
                    "document_id": document.id,
                    "page_content": document.page_content,
                    "metadata": document.metadata,
                },
            )
            for document, embedding in zip(documents, embeddings, strict=True)
        ]
        await self.client.upsert(collection_name=self.collection_name, points=points)

    async def search(
        self,
        query_embedding: Sequence[float],
        *,
        limit: int = 4,
        filters: Mapping[str, str] | None = None,
    ) -> list[VectorSearchResult]:
        query = _validated_vector(query_embedding, self.dimensions)
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        await self.initialize()

        query_filter = None
        if filters:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key=f"metadata.{key}",
                        match=models.MatchValue(value=value),
                    )
                    for key, value in filters.items()
                ]
            )
        response = await self.client.query_points(
            collection_name=self.collection_name,
            query=query,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        results: list[VectorSearchResult] = []
        for point in response.points:
            payload = point.payload
            if not isinstance(payload, dict):
                raise TypeError("Qdrant returned a point without a valid payload")
            metadata = payload.get("metadata")
            document_id = payload.get("document_id")
            page_content = payload.get("page_content")
            if (
                not isinstance(metadata, dict)
                or not isinstance(document_id, str)
                or not isinstance(page_content, str)
            ):
                raise TypeError("Qdrant returned a malformed document payload")
            results.append(
                VectorSearchResult(
                    chunk=ArticleChunk(
                        id=document_id,
                        page_content=page_content,
                        metadata=metadata,
                    ),
                    score=float(point.score),
                )
            )
        return results

    async def delete(self, ids: Sequence[str]) -> None:
        if not ids:
            return
        await self.initialize()
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(points=[_qdrant_id(item) for item in ids]),
        )

    async def clear(self) -> None:
        if await self.client.collection_exists(self.collection_name):
            await self.client.delete_collection(self.collection_name)
        self._initialized = False
        await self.initialize()

    async def count(self) -> int:
        await self.initialize()
        result = await self.client.count(collection_name=self.collection_name, exact=True)
        return result.count

    async def health(self) -> bool:
        return await self.client.collection_exists(self.collection_name)

    async def aclose(self) -> None:
        await self.client.close()


def _validated_vector(values: Sequence[float], dimensions: int) -> list[float]:
    vector = [float(value) for value in values]
    if len(vector) != dimensions:
        raise ValueError(f"expected a {dimensions}-dimensional vector, got {len(vector)}")
    if not all(math.isfinite(value) for value in vector):
        raise ValueError("vector values must be finite")
    return vector


def _copy_chunk(chunk: ArticleChunk) -> ArticleChunk:
    return ArticleChunk(
        id=chunk.id,
        page_content=chunk.page_content,
        metadata=deepcopy(chunk.metadata),
    )


def _matches_filters(
    chunk: ArticleChunk, filters: Mapping[str, str] | None
) -> bool:
    return filters is None or all(chunk.metadata.get(key) == value for key, value in filters.items())


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _qdrant_id(document_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"clouddesk-knowledge:{document_id}"))


async def create_vector_store(
    settings: Settings | None = None,
) -> VectorStoreService:
    settings = settings or get_settings()
    if settings.vector_store == "memory":
        return InMemoryVectorStore(dimensions=settings.embedding_dimensions)
    if not settings.qdrant_url or not settings.qdrant_url.strip():
        raise ValueError("QDRANT_URL is required when VECTOR_STORE=qdrant")

    api_key = (
        settings.qdrant_api_key.get_secret_value()
        if settings.qdrant_api_key is not None
        else None
    )
    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=api_key)
    store = QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection,
        dimensions=settings.embedding_dimensions,
    )
    await store.initialize()
    return store
