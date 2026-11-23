from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agents.rules import matching_escalation_rules
from agents.specialists import ResolutionAgent, SupervisorAgent
from backend.app.core.llm import FakeLLM
from backend.app.schemas.common import TicketCategory
from backend.app.schemas.workflow import Diagnosis, DiagnosisStep
from rag.chunking import chunk_article, load_article_files
from rag.embeddings import FakeEmbeddings
from rag.retriever import HybridRetriever
from rag.vector_store import InMemoryVectorStore

_EVAL_CASES_PATH = Path(__file__).parent / "datasets" / "eval_cases.json"
_CLASSIFICATION_ACCURACY = 0.80
_RETRIEVAL_HIT_RATE_AT_3 = 0.75
_ESCALATION_CORRECTNESS = 0.90
_CITATION_RATE = 0.90
_GROUNDING_RATE = 0.90


def _load_cases() -> list[dict[str, Any]]:
    payload = json.loads(_EVAL_CASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("Evaluation cases must be stored as a JSON list")
    for case in payload:
        TicketCategory(case["expected_category"])
        if not isinstance(case.get("expected_escalation"), bool):
            raise TypeError(f"{case['id']} must define expected_escalation")
    return payload


@pytest.mark.asyncio
async def test_offline_quality_metrics_meet_phase_thresholds() -> None:
    cases = _load_cases()
    articles = load_article_files()
    chunks = [chunk for article in articles for chunk in chunk_article(article)]
    embeddings = FakeEmbeddings()
    vector_store = InMemoryVectorStore()
    await vector_store.add_documents(
        chunks,
        [embeddings.embed_query(chunk.page_content) for chunk in chunks],
    )
    retriever = HybridRetriever(chunks, vector_store, embeddings)
    supervisor = SupervisorAgent(FakeLLM())
    resolver = ResolutionAgent(FakeLLM())

    classifications = 0
    retrieval_hits = 0
    retrieval_cases = 0
    escalation_matches = 0
    citations = 0
    citation_cases = 0
    grounded_steps = 0
    diagnosis_steps = 0

    diagnosis = Diagnosis(
        probable_causes=["The reported behavior needs further verification."],
        steps=[
            DiagnosisStep(
                number=1,
                instruction="Confirm the affected account and reproduce the reported behavior.",
            ),
            DiagnosisStep(
                number=2,
                instruction="Compare the results with the relevant support guidance.",
            ),
        ],
        service_status=None,
    )

    for case in cases:
        text = f"{case['subject']}\n{case['body']}"
        classification = await supervisor.understand(case["subject"], case["body"])
        classifications += classification.category.value == case["expected_category"]

        expected_article = case.get("expected_article")
        if expected_article is not None:
            category = TicketCategory(case["expected_category"])
            evidence = await retriever.retrieve(
                text,
                category=category.value,
                top_k=3,
            )
            retrieval_cases += 1
            retrieval_hits += any(
                item.article_id == expected_article for item in evidence
            )
        else:
            evidence = await retriever.retrieve(text, top_k=3)

        policy_escalation = bool(
            matching_escalation_rules(text, case.get("plan_name"))
        )
        escalation_matches += (
            policy_escalation == case["expected_escalation"]
        )

        resolution = await resolver.run(
            case["subject"],
            case["body"],
            classification,
            diagnosis,
            evidence,
        )
        if evidence:
            citation_cases += 1
            citations += resolution.output_valid and all(
                f"[{item.title}]({item.url})" in resolution.customer_reply
                and item.source in resolution.customer_reply
                for item in evidence
            )

        diagnosis_steps += len(diagnosis.steps)
        grounded_steps += sum(
            step.instruction in resolution.customer_reply
            for step in diagnosis.steps
        )

    classification_accuracy = classifications / len(cases)
    retrieval_hit_rate = retrieval_hits / retrieval_cases
    escalation_correctness = escalation_matches / len(cases)
    citation_rate = citations / citation_cases
    grounding_rate = grounded_steps / diagnosis_steps

    assert classification_accuracy >= _CLASSIFICATION_ACCURACY, (
        f"classification accuracy {classification_accuracy:.3f} "
        f"is below {_CLASSIFICATION_ACCURACY:.2f}"
    )
    assert retrieval_hit_rate >= _RETRIEVAL_HIT_RATE_AT_3, (
        f"retrieval hit-rate@3 {retrieval_hit_rate:.3f} "
        f"is below {_RETRIEVAL_HIT_RATE_AT_3:.2f}"
    )
    assert escalation_correctness >= _ESCALATION_CORRECTNESS, (
        f"escalation correctness {escalation_correctness:.3f} "
        f"is below {_ESCALATION_CORRECTNESS:.2f}"
    )
    assert citation_rate >= _CITATION_RATE, (
        f"citation rate {citation_rate:.3f} is below {_CITATION_RATE:.2f}"
    )
    assert grounding_rate >= _GROUNDING_RATE, (
        f"grounding rate {grounding_rate:.3f} is below {_GROUNDING_RATE:.2f}"
    )
