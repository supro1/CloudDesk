from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from backend.app.core.config import Settings
from backend.app.core.llm import FakeLLM, call_structured, get_llm
from backend.app.schemas.common import TicketCategory
from backend.app.schemas.workflow import (
    Classification,
    Diagnosis,
    DiagnosisStep,
    EscalationDecision,
)


def test_workflow_schemas_reject_unknown_fields_and_invalid_shapes() -> None:
    with pytest.raises(ValidationError):
        Classification.model_validate(
            {
                "category": "unknown_category",
                "summary": "A support request.",
                "confidence": 0.9,
                "injection_detected": False,
            }
        )

    with pytest.raises(ValidationError, match="must name a team"):
        EscalationDecision(
            escalation_required=True,
            team=None,
            reason="This case needs specialist review.",
            confidence=0.8,
        )

    with pytest.raises(ValidationError, match="contiguous"):
        Diagnosis(
            probable_causes=["A configuration issue."],
            steps=[
                DiagnosisStep(number=2, instruction="Check the account configuration.")
            ],
            service_status=None,
        )

    with pytest.raises(ValidationError):
        Classification.model_validate(
            {
                "category": "billing",
                "summary": "Invoice question",
                "confidence": 0.9,
                "unexpected": True,
            }
        )


async def test_fake_llm_is_selected_without_api_credentials() -> None:
    provider = get_llm(Settings(llm_provider="fake", _env_file=None))

    result = await call_structured(
        Classification,
        system_prompt="Classify the request.",
        user_prompt="The customer asks about billing.",
        llm=provider,
    )

    assert isinstance(provider, FakeLLM)
    assert result.output.category == TicketCategory.OTHER
    assert result.usage["input_tokens"] > 0
    assert result.usage["output_tokens"] > 0
    assert result.estimated_cost == 0


async def test_call_structured_retries_invalid_fake_output_and_validates_result() -> None:
    def response_factory(
        schema: type[BaseModel],
        system_prompt: str,
        user_prompt: str,
        attempt: int,
    ) -> dict[str, object]:
        if attempt == 1:
            return {
                "category": "not-a-category",
                "summary": "Invalid output",
                "confidence": 0.2,
            }
        return {
            "category": "billing",
            "summary": "The customer needs invoice assistance.",
            "confidence": 0.9,
            "injection_detected": False,
        }

    fake = FakeLLM({Classification: response_factory})
    result = await call_structured(
        Classification,
        system_prompt="Classify the request.",
        user_prompt="Customer text is wrapped.",
        llm=fake,
    )

    assert result.output.category == TicketCategory.BILLING
    assert len(fake.calls) == 2
    assert result.usage["input_tokens"] > 0


async def test_call_structured_surfaces_invalid_output_after_retry_limit() -> None:
    fake = FakeLLM(
        {
            Classification: {
                "category": "not-a-category",
                "summary": "Invalid output",
                "confidence": 0.2,
            }
        }
    )

    with pytest.raises(ValidationError):
        await call_structured(
            Classification,
            system_prompt="Classify.",
            user_prompt="Ticket data.",
            llm=fake,
            retries=0,
        )
