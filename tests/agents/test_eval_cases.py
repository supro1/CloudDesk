from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.specialists import SupervisorAgent
from backend.app.core.llm import FakeLLM
from backend.app.schemas.common import TicketCategory

_EVAL_CASES_PATH = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "datasets"
    / "eval_cases.json"
)


def _load_cases() -> list[dict[str, Any]]:
    payload = json.loads(_EVAL_CASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("Evaluation cases must be stored as a JSON list")
    for case in payload:
        TicketCategory(case["expected_category"])
    return payload


async def test_eval_cases_cover_each_supported_category_and_match_supervisor_rules() -> None:
    cases = _load_cases()
    categories = {case["expected_category"] for case in cases}
    agent = SupervisorAgent(FakeLLM())

    assert categories == {category.value for category in TicketCategory}
    for case in cases:
        result = await agent.understand(case["subject"], case["body"])
        assert result.category.value == case["expected_category"], case["id"]
        if case["id"] == "CD-1013":
            assert result.injection_detected
