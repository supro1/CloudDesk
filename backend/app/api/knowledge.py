from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.models.entities import SupportArticle
from backend.app.repositories import SupportArticleRepository
from backend.app.schemas.knowledge import (
    KnowledgeArticlePageResponse,
    KnowledgeArticleResponse,
    KnowledgeReindexResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from backend.app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


def _article_response(article: SupportArticle) -> KnowledgeArticleResponse:
    return KnowledgeArticleResponse.model_validate(article)


def _knowledge_service(request: Request) -> KnowledgeService:
    service: KnowledgeService | None = getattr(request.app.state, "knowledge_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Knowledge search is not initialized")
    return service


@router.get("", response_model=KnowledgeArticlePageResponse)
async def list_knowledge_articles(
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> KnowledgeArticlePageResponse:
    repository = SupportArticleRepository(session)
    articles = await repository.list_published(limit=limit, offset=offset)
    return KnowledgeArticlePageResponse(
        items=[_article_response(article) for article in articles],
        total=await repository.count_published(),
        limit=limit,
        offset=offset,
    )


@router.get("/{article_id}", response_model=KnowledgeArticleResponse)
async def get_knowledge_article(
    article_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
) -> KnowledgeArticleResponse:
    repository = SupportArticleRepository(session)
    article = await repository.get_by_slug(article_id)
    if article is None:
        article = await repository.get(article_id)
    if article is None or not article.is_published:
        raise HTTPException(status_code=404, detail="Knowledge article not found")
    return _article_response(article)


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    body: KnowledgeSearchRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    service: Annotated[KnowledgeService, Depends(_knowledge_service)],
) -> KnowledgeSearchResponse:
    articles = await SupportArticleRepository(session).list_published(limit=10_000)
    evidence = await service.search(
        articles,
        body.query,
        category=body.category,
        mode=body.mode,
        top_k=body.top_k,
    )
    return KnowledgeSearchResponse(query=body.query, items=evidence)


@router.post("/reindex", response_model=KnowledgeReindexResponse)
async def reindex_knowledge(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("admin"))],
    service: Annotated[KnowledgeService, Depends(_knowledge_service)],
) -> KnowledgeReindexResponse:
    settings = request.app.state.settings
    result = await service.reindex(
        session,
        settings.sample_data_dir / "knowledge_base",
    )
    return KnowledgeReindexResponse(
        article_count=result.article_count,
        chunk_count=result.chunk_count,
    )
