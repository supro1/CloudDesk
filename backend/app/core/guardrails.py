from __future__ import annotations

import html
import re
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlsplit

from memory.secret_scrub import contains_secret

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:ignore|forget|disregard|override)\b.{0,50}"
        r"\b(?:previous|prior|above|system|developer|all)\b.{0,40}"
        r"\b(?:instructions?|rules?|prompts?)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(?:reveal|show|print|repeat|expose)\b.{0,35}"
        r"\b(?:system|developer|hidden)\b.{0,20}"
        r"\b(?:prompt|instructions?|message)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(?:export|dump|download|exfiltrate)\b.{0,50}"
        r"\b(?:all )?(?:customer|user|account|tenant) "
        r"(?:records?|data|files?)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(?:call|invoke|run|execute)\b.{0,40}"
        r"\b(?:tool|function|command)\b.{0,40}"
        r"\b(?:export|delete|refund|admin|all records?)\b",
        re.IGNORECASE | re.DOTALL,
    ),
)

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_DEFAULT_INTERNAL_HOSTS = frozenset(
    {"api", "backend", "db", "postgres", "qdrant", "redis"}
)


@dataclass(frozen=True)
class OutputValidationResult:
    valid: bool
    issues: tuple[str, ...]


def scan_for_injection(text: str) -> bool:
    """Flag common instruction-override and unauthorized-data request patterns."""
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)


def wrap_untrusted(text: str) -> str:
    """Place external text in delimiters while escaping markup that could close them."""
    return f"<untrusted_content>{html.escape(text, quote=False)}</untrusted_content>"


def _is_internal_host(host: str) -> bool:
    normalized = host.rstrip(".").casefold()
    if (
        normalized in _DEFAULT_INTERNAL_HOSTS
        or normalized == "localhost"
        or normalized.endswith((".local", ".internal"))
    ):
        return True
    try:
        address = ip_address(normalized)
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_unspecified
    )


def _contains_internal_url(text: str) -> bool:
    for match in _URL_PATTERN.finditer(text):
        candidate = match.group().rstrip(".,;:!?)]}")
        if _is_internal_host(urlsplit(candidate).hostname or ""):
            return True
    return False


def validate_customer_output(
    text: str,
    *,
    internal_urls: tuple[str, ...] | list[str] = (),
    forbidden_values: tuple[str, ...] | list[str] = (),
) -> OutputValidationResult:
    """Identify secrets, internal URLs, and caller-supplied cross-customer data."""
    issues: list[str] = []
    if not text.strip():
        issues.append("empty_output")
    if contains_secret(text):
        issues.append("secret_detected")
    if _contains_internal_url(text) or any(
        url and url.casefold() in text.casefold() for url in internal_urls
    ):
        issues.append("internal_url_detected")
    lowered_text = text.casefold()
    if any(
        value.strip()
        and len(value.strip()) >= 3
        and value.strip().casefold() in lowered_text
        for value in forbidden_values
    ):
        issues.append("other_customer_data_detected")
    return OutputValidationResult(valid=not issues, issues=tuple(issues))
