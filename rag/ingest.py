from __future__ import annotations

import asyncio

from backend.app.core.config import Settings, get_settings
from backend.app.core.database import create_tables, dispose_engine, session_factory
from backend.app.services.knowledge_service import KnowledgeService
from rag.embeddings import FakeEmbeddings
from rag.vector_store import create_vector_store


async def ingest_knowledge_base(settings: Settings | None = None) -> tuple[int, int]:
    settings = settings or get_settings()
    await create_tables()
    service: KnowledgeService | None = None
    try:
        service = KnowledgeService(
            await create_vector_store(settings),
            FakeEmbeddings(dimensions=settings.embedding_dimensions),
        )
        async with session_factory() as session:
            result = await service.reindex(
                session,
                settings.sample_data_dir / "knowledge_base",
            )
        return result.article_count, result.chunk_count
    finally:
        try:
            if service is not None:
                await service.close()
        finally:
            await dispose_engine()


async def main() -> None:
    article_count, chunk_count = await ingest_knowledge_base()
    print(f"Indexed {article_count} knowledge articles into {chunk_count} chunks.")


if __name__ == "__main__":
    asyncio.run(main())
