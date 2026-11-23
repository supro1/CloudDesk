from __future__ import annotations

import pytest

from agents.state import append_values, merge_usage


def test_state_reducers_append_and_sum_usage() -> None:
    assert append_values(["understand_ticket"], ["classify_severity"]) == [
        "understand_ticket",
        "classify_severity",
    ]
    assert merge_usage(
        {"input_tokens": 10, "output_tokens": 2},
        {"input_tokens": 5, "output_tokens": 3},
    ) == {"input_tokens": 15, "output_tokens": 5}


def test_usage_reducer_rejects_non_integer_counts() -> None:
    with pytest.raises(TypeError, match="must be an integer"):
        merge_usage({}, {"input_tokens": True})  # type: ignore[dict-item]
