from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from backend.app.core.guardrails import scan_for_injection
from backend.app.schemas.common import TicketCategory

__all__ = [
    "ESCALATION_RULES",
    "EscalationRule",
    "matching_escalation_rules",
    "rule_category",
    "rule_severity",
    "scan_for_injection",
]

Severity = Literal["low", "medium", "high", "critical"]

_SEVERITY_LEVELS: dict[Severity, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

_CATEGORY_RULES: tuple[tuple[TicketCategory, tuple[re.Pattern[str], ...]], ...] = (
    (
        TicketCategory.SECURITY,
        (
            re.compile(
                r"\b(?:security incident|data breach|compromised|"
                r"suspicious (?:logins?|sign.?ins?)|unauthori[sz]ed access)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        TicketCategory.ACCOUNT,
        (
            re.compile(
                r"\b(?:delete|close|erase|deactivate)\b.{0,35}"
                r"\b(?:account|workspace|data)\b|\baccount deletion\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        TicketCategory.BILLING,
        (
            re.compile(
                r"\b(?:billing|invoice|refund|charged?|chargeback|payment|"
                r"subscription|seat count)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        TicketCategory.LOGIN_ISSUE,
        (
            re.compile(
                r"\b(?:login|log in|sign.?in|locked out|sso|mfa|"
                r"authentication|password reset)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        TicketCategory.API_FAILURE,
        (
            re.compile(
                r"\b(?:api|http\s*[45]\d\d|429|rate limit|endpoint|"
                r"api request)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        TicketCategory.STORAGE_QUOTA,
        (
            re.compile(
                r"\b(?:storage quota|quota exceeded|storage limit|"
                r"upload(?:s)? fail|out of storage)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        TicketCategory.WORKSPACE_PERMISSIONS,
        (
            re.compile(
                r"\b(?:permission|sharing|share a folder|invite (?:an )?"
                r"external|access setting|workspace access|share(?: a)? folder|"
                r"external sharing)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        TicketCategory.INTEGRATION,
        (
            re.compile(
                r"\b(?:integration|slack|webhook|connected app|"
                r"third.party app)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        TicketCategory.FEATURE_REQUEST,
        (
            re.compile(
                r"\b(?:feature request|please add|would like to have|"
                r"request a feature|suggestion for|dark mode|dark theme)\b",
                re.IGNORECASE,
            ),
        ),
    ),
)


@dataclass(frozen=True)
class EscalationRule:
    name: str
    team: str
    reason: str
    pattern: re.Pattern[str]
    minimum_severity: Severity
    requires_enterprise: bool = False


ESCALATION_RULES: tuple[EscalationRule, ...] = (
    EscalationRule(
        name="security_incident",
        team="security",
        reason="Suspected compromise or unauthorized access requires security review.",
        pattern=re.compile(
            r"\b(?:security incident|breach|compromised|suspicious "
            r"(?:logins?|sign.?ins?)|unauthori[sz]ed access|account takeover)\b",
            re.IGNORECASE,
        ),
        minimum_severity="critical",
    ),
    EscalationRule(
        name="data_loss",
        team="data_recovery",
        reason="Missing or lost customer data requires specialist investigation.",
        pattern=re.compile(
            r"\b(?:data loss|files? (?:have |has )?(?:disappeared|missing|"
            r"gone)|missing files|lost files|deleted files)\b",
            re.IGNORECASE,
        ),
        minimum_severity="critical",
    ),
    EscalationRule(
        name="payment_dispute",
        team="billing",
        reason="A disputed or unauthorized payment requires billing review.",
        pattern=re.compile(
            r"\b(?:payment dispute|chargeback|dispute (?:a |the )?charge|"
            r"unauthori[sz]ed charge|fraudulent charge)\b",
            re.IGNORECASE,
        ),
        minimum_severity="high",
    ),
    EscalationRule(
        name="account_deletion",
        team="privacy_compliance",
        reason="Account or data deletion requires ownership and privacy-policy review.",
        pattern=re.compile(
            r"\b(?:gdpr|dsar|data erasure|erase (?:all |the )?data|"
            r"delete (?:the |our |my |legacy )?(?:account|workspace|data)|"
            r"account deletion)\b",
            re.IGNORECASE,
        ),
        minimum_severity="high",
    ),
    EscalationRule(
        name="legal_request",
        team="legal",
        reason="A legal or regulatory matter requires specialist handling.",
        pattern=re.compile(
            r"\b(?:lawsuit|litigation|subpoena|legal hold|regulatory "
            r"request|legal counsel)\b",
            re.IGNORECASE,
        ),
        minimum_severity="high",
    ),
    EscalationRule(
        name="enterprise_service_outage",
        team="incident_response",
        reason="A broad Enterprise service outage requires incident response.",
        pattern=re.compile(
            r"\b(?:service outage|service is down|widespread outage|"
            r"whole team (?:is )?(?:unable|cannot|can't)|all users "
            r"(?:are|cannot|can't))\b",
            re.IGNORECASE,
        ),
        minimum_severity="high",
        requires_enterprise=True,
    ),
)


def rule_category(text: str) -> TicketCategory | None:
    """Return a deterministic category for clear keyword matches, else None."""
    for category, patterns in _CATEGORY_RULES:
        if any(pattern.search(text) for pattern in patterns):
            return category
    return None


def matching_escalation_rules(
    text: str,
    plan_name: str | None = None,
) -> list[EscalationRule]:
    """Return matching policy rules in priority order, with the primary rule first."""
    is_enterprise = plan_name is not None and "enterprise" in plan_name.casefold()
    return [
        rule
        for rule in ESCALATION_RULES
        if (not rule.requires_enterprise or is_enterprise) and rule.pattern.search(text)
    ]


def rule_severity(
    text: str,
    severity: Severity,
    plan_name: str | None = None,
) -> tuple[Severity, str | None]:
    """Raise a proposed severity when a deterministic policy requires it; never lower it."""
    if severity not in _SEVERITY_LEVELS:
        raise ValueError(f"Unsupported severity: {severity}")

    matching_rules = matching_escalation_rules(text, plan_name)
    if not matching_rules:
        return severity, None

    required = matching_rules[0]
    if _SEVERITY_LEVELS[severity] >= _SEVERITY_LEVELS[required.minimum_severity]:
        return severity, (
            f"{required.reason} Existing {severity} severity is retained."
        )
    return required.minimum_severity, required.reason
