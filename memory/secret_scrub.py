from __future__ import annotations

import re

SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|"
        r"client[_ -]?secret|password|passwd|secret)\b\s*[:=]\s*"
        r"(?P<quote>['\"]?)(?!\[REDACTED\])(?P<value>[^\s'\";,]+)(?P=quote)"
    ),
    re.compile(r"(?i)\bbearer\s+(?P<value>[A-Za-z0-9._~+/-]+=*)"),
    re.compile(
        r"\b(?:sk-(?:live|test|proj)-|sk_live_|gh[pousr]_|xox[baprs]-|AKIA)"
        r"[A-Za-z0-9_-]{12,}\b"
    ),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        r".+?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        re.DOTALL,
    ),
    re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"),
)

_CARD_PATTERN_INDEX = 5
_REDACTION = "[REDACTED]"


def _passes_luhn(digits: str) -> bool:
    total = 0
    parity = len(digits) % 2
    for index, character in enumerate(digits):
        digit = int(character)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _secret_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern_index, pattern in enumerate(SECRET_PATTERNS):
        for match in pattern.finditer(text):
            if pattern_index == 0 or pattern_index == 1:
                start, end = match.span("value")
            elif pattern_index == _CARD_PATTERN_INDEX:
                start, end = match.span()
                if not _passes_luhn(re.sub(r"\D", "", match.group())):
                    continue
            else:
                start, end = match.span()
            if start < end:
                spans.append((start, end))

    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def contains_secret(text: str) -> bool:
    """Return whether text contains a recognized credential or payment-card number."""
    return bool(_secret_spans(text))


def scrub(text: str) -> str:
    """Redact recognized secret values while preserving surrounding explanatory text."""
    scrubbed = text
    for start, end in reversed(_secret_spans(text)):
        scrubbed = scrubbed[:start] + _REDACTION + scrubbed[end:]
    return scrubbed


scrub_secrets = scrub

__all__ = ["SECRET_PATTERNS", "contains_secret", "scrub", "scrub_secrets"]
