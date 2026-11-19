import pytest

from backend.app.core.config import Settings
from backend.app.tools.policy import ToolPolicy


@pytest.mark.parametrize(
    "tool_name",
    [
        "get_customer",
        "get_subscription",
        "get_ticket_history",
        "search_docs",
        "check_service_status",
        "update_ticket",
        "create_escalation",
    ],
)
def test_known_non_consequential_tools_do_not_require_approval(
    tool_name: str,
) -> None:
    policy = ToolPolicy(Settings(_env_file=None))

    assert not policy.evaluate(tool_name).approval_required


def test_setting_reset_and_unknown_tools_always_require_approval() -> None:
    policy = ToolPolicy(Settings(_env_file=None))

    assert policy.evaluate("reset_demo_setting").approval_required
    assert policy.evaluate("unregistered_tool").approval_required
    assert policy.requires_approval("unregistered_tool")


def test_refunds_require_approval_by_default() -> None:
    policy = ToolPolicy(Settings(_env_file=None))

    decision = policy.evaluate("create_refund_request", {"amount": "1.00"})

    assert decision.approval_required
    assert decision.reason == "Refund requests require human approval."


@pytest.mark.parametrize(
    ("amount", "approval_required"),
    [
        ("25", False),
        ("25.01", True),
        (None, True),
        ("not-a-number", True),
        ("-1", True),
        ("Infinity", True),
        (True, True),
    ],
)
def test_refund_amount_limit_is_fail_closed(
    amount: object,
    approval_required: bool,
) -> None:
    settings = Settings(
        _env_file=None,
        approval_required_for_refunds=False,
        max_refund_without_approval=25,
    )
    decision = ToolPolicy(settings).evaluate(
        "create_refund_request",
        {"amount": amount},
    )

    assert decision.approval_required is approval_required
