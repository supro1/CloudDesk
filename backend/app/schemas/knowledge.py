from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.schemas.common import TicketCategory
from rag.retriever import Evidence

KnowledgeSearchMode = Literal["hybrid", "semantic", "keyword"]


class KnowledgeArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    title: str
    category: TicketCategory | None
    tags: list[str]
    summary: str
    content: str
    created_at: datetime
    updated_at: datetime


class KnowledgeArticlePageResponse(BaseModel):
    items: list[KnowledgeArticleResponse]
    total: int
    limit: int
    offset: int


class KnowledgeSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=1000)
    category: TicketCategory | None = None
    mode: KnowledgeSearchMode = "hybrid"
    top_k: int = Field(default=3, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class KnowledgeSearchResponse(BaseModel):
    query: str
    items: list[Evidence]


class KnowledgeReindexResponse(BaseModel):
    article_count: int
    chunk_count: int
