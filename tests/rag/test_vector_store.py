from types import SimpleNamespace

import pytest
from qdrant_client import models

from backend.app.core.config import Settings
from backend.app.schemas.common import TicketCategory
from rag.chunking import ArticleChunk
from rag.embeddings import FakeEmbeddings
from rag.vector_store import InMemoryVectorStore, QdrantVectorStore, create_vector_store


def _chunk(
    document_id: str,
    content: str,
    category: str = "login_issue",
) -> ArticleChunk:
    return ArticleChunk(
        id=document_id,
        page_content=content,
        metadata={
            "article_slug": document_id,
            "title": document_id,
            "category": category,
            "source": f"kb://{document_id}#section",
        },
    )


class _FakeQdrantClient:
    def __init__(self) -> None:
        self.exists = False
        self.created = 0
        self.collection_name = ""
        self.vector_config = None
        self.points = []
        self.query_filter = None
        self.query_limit = 0
        self.with_payload = False
        self.deleted = []
        self.last_query = []
        self.count_exact = False

    async def collection_exists(self, collection_name: str) -> bool:
        self.collection_name = collection_name
        return self.exists

    async def create_collection(
        self,
        collection_name: str,
        vectors_config: models.VectorParams,
    ) -> None:
        self.created += 1
        self.collection_name = collection_name
        self.vector_config = vectors_config
        self.exists = True

    async def upsert(
        self,
        collection_name: str,
        points: list[models.PointStruct],
    ) -> None:
        self.collection_name = collection_name
        self.points = points

    async def query_points(
        self,
        collection_name: str,
        query: list[float],
        query_filter: models.Filter | None,
        limit: int,
        with_payload: bool,
    ) -> SimpleNamespace:
        self.collection_name = collection_name
        self.last_query = query
        self.query_filter = query_filter
        self.query_limit = limit
        self.with_payload = with_payload
        point = self.points[0]
        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    payload=point.payload,
                    score=0.9,
                )
            ]
        )

    async def delete(
        self,
        collection_name: str,
        points_selector: models.PointIdsList,
    ) -> None:
        self.collection_name = collection_name
        self.deleted = points_selector.points
        self.points = [point for point in self.points if point.id not in self.deleted]

    async def count(self, collection_name: str, exact: bool) -> SimpleNamespace:
        self.collection_name = collection_name
        self.count_exact = exact
        return SimpleNamespace(count=len(self.points))


@pytest.mark.asyncio
async def test_in_memory_store_searches_by_similarity_and_filters() -> None:
    embeddings = FakeEmbeddings(dimensions=64)
    store = InMemoryVectorStore(dimensions=64)
    documents = [
        _chunk("login", "Troubleshoot login problems", "login_issue"),
        _chunk("billing", "Understand invoice charges", "billing"),
    ]
    vectors = embeddings.embed_documents([item.page_content for item in documents])
    await store.add_documents(documents, vectors)

    results = await store.search(embeddings.embed_query("login problems"), limit=2)

    assert [result.chunk.id for result in results] == ["login", "billing"]
    assert results[0].score > 0
    filtered = await store.search(
        embeddings.embed_query("login problems"),
        limit=2,
        filters={"category": TicketCategory.LOGIN_ISSUE.value},
    )
    assert [result.chunk.id for result in filtered] == ["login"]
    assert await store.count() == 2
    assert await store.health()


@pytest.mark.asyncio
async def test_in_memory_store_upserts_and_deletes_by_document_id() -> None:
    embeddings = FakeEmbeddings(dimensions=4)
    store = InMemoryVectorStore(dimensions=4)
    document = _chunk("login", "Original troubleshooting")
    await store.add_documents([document], [embeddings.embed_query(document.page_content)])
    replacement = _chunk("login", "Updated troubleshooting")
    await store.add_documents(
        [replacement],
        [embeddings.embed_query(replacement.page_content)],
    )

    assert await store.count() == 1
    assert (await store.search(embeddings.embed_query("updated troubleshooting")))[0].chunk.page_content == (
        "Updated troubleshooting"
    )

    await store.delete(["login"])
    assert await store.count() == 0


@pytest.mark.asyncio
async def test_in_memory_store_rejects_mismatched_documents_and_vectors() -> None:
    store = InMemoryVectorStore(dimensions=2)
    with pytest.raises(ValueError, match="same length"):
        await store.add_documents([_chunk("login", "Help")], [])
    with pytest.raises(ValueError, match="2-dimensional"):
        await store.add_documents([_chunk("login", "Help")], [[1.0]])
    with pytest.raises(ValueError, match="finite"):
        await store.search([float("inf"), 0.0])


@pytest.mark.asyncio
async def test_qdrant_store_creates_collection_upserts_searches_and_deletes() -> None:
    client = _FakeQdrantClient()
    store = QdrantVectorStore(client, "knowledge", dimensions=2)
    document = _chunk("login", "Login support")

    await store.add_documents([document], [[1.0, 0.0]])
    results = await store.search([1.0, 0.0], filters={"category": "login_issue"})

    assert client.created == 1
    assert client.vector_config is not None
    assert client.vector_config.size == 2
    assert results[0].chunk == document
    assert results[0].score == pytest.approx(0.9)
    assert client.query_filter.must[0].key == "metadata.category"
    assert client.last_query == [1.0, 0.0]
    assert client.query_limit == 4
    assert client.with_payload
    assert await store.count() == 1
    assert client.count_exact
    assert await store.health()

    await store.delete(["login"])
    assert len(client.deleted) == 1
    assert await store.count() == 0


@pytest.mark.asyncio
async def test_vector_store_factory_uses_configured_backend() -> None:
    settings = Settings(vector_store="memory", embedding_dimensions=32, _env_file=None)

    store = await create_vector_store(settings)
    assert isinstance(store, InMemoryVectorStore)
    assert store.dimensions == 32


@pytest.mark.asyncio
@pytest.mark.parametrize("qdrant_url", [None, ""])
async def test_qdrant_factory_requires_url(qdrant_url: str | None) -> None:
    settings = Settings(
        vector_store="qdrant",
        qdrant_url=qdrant_url,
        _env_file=None,
    )

    with pytest.raises(ValueError, match="QDRANT_URL"):
        await create_vector_store(settings)
