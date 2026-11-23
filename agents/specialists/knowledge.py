from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

from agents.specialists._tools import execute_tool
from backend.app.schemas.common import TicketCategory
from backend.app.schemas.workflow import Evidence, KnowledgeResult, PreviousCase
from backend.app.tools.registry import ToolRegistry
from rag.retriever import RetrievalMode

_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
_STOPWORDS = frozenset(
    {
        "a",
        "after",
        "and",
        "for",
        "in",
        "is",
        "it",
        "of",
        "our",
        "the",
        "this",
        "to",
        "was",
        "we",
        "with",
    }
)
_DEFAULT_CASES_PATH = (
    Path(__file__).resolve().parents[2]
    / "sample_data"
    / "previous_resolutions.json"
)


class KnowledgeAgent:
    """Retrieve cited articles and rank similar resolved examples by word overlap."""

    def __init__(
        self,
        tools: ToolRegistry,
        previous_cases: Sequence[PreviousCase] | None = None,
        *,
        cases_path: Path = _DEFAULT_CASES_PATH,
    ) -> None:
        self.tools = tools
        self.previous_cases = (
            tuple(previous_cases)
            if previous_cases is not None
            else tuple(_load_previous_cases(cases_path))
        )

    async def run(
        self,
        query: str,
        *,
        category: TicketCategory | None = None,
        mode: RetrievalMode = "hybrid",
        top_k: int = 3,
    ) -> KnowledgeResult:
        if not query.strip():
            raise ValueError("query must not be empty")
        if mode not in {"hybrid", "semantic", "keyword"}:
            raise ValueError(f"Unsupported retrieval mode: {mode}")
        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        raw_evidence = await execute_tool(
            self.tools,
            "search_docs",
            {
                "query": query,
                "category": category.value if category is not None else None,
                "mode": mode,
                "top_k": top_k,
            },
        )
        if not isinstance(raw_evidence, list):
            raise TypeError("search_docs must return a list of evidence records")
        evidence = [Evidence.model_validate(item) for item in raw_evidence]
        return KnowledgeResult(
            evidence=evidence,
            similar_cases=self.similar_cases(query, top_k=top_k),
        )

    def similar_cases(
        self,
        query: str,
        *,
        top_k: int = 3,
        minimum_similarity: float = 0.05,
    ) -> list[PreviousCase]:
        if top_k < 1:
            raise ValueError("top_k must be greater than zero")
        if not 0 <= minimum_similarity <= 1:
            raise ValueError("minimum_similarity must be between zero and one")
        query_tokens = _tokens(query)
        if not query_tokens:
            return []

        ranked: list[tuple[PreviousCase, float]] = []
        for case in self.previous_cases:
            case_tokens = _tokens(" ".join([case.resolution, *case.steps]))
            union = query_tokens | case_tokens
            similarity = len(query_tokens & case_tokens) / len(union) if union else 0
            if similarity >= minimum_similarity and similarity > 0:
                ranked.append((case, similarity))
        ranked.sort(key=lambda result: result[1], reverse=True)
        return [
            case.model_copy(update={"similarity": score})
            for case, score in ranked[:top_k]
        ]


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_PATTERN.findall(text.casefold())
        if token not in _STOPWORDS
    }


def _load_previous_cases(path: Path) -> list[PreviousCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError(f"Previous-resolution data in {path} must be a list")
    return [PreviousCase.model_validate(item) for item in payload]


__all__ = ["KnowledgeAgent"]
