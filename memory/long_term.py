from __future__ import annotations

import re
from collections.abc import Sequence

from backend.app.models.entities import CustomerMemory
from backend.app.repositories.workflow import CustomerMemoryRepository
from memory.secret_scrub import scrub

MemoryKind = str
ALLOWED_MEMORY_KINDS = frozenset(
    {"preference", "past_issue", "troubleshooting", "note"}
)
MAX_RECALL_NOTES = 10


class LongTermMemory:
    """Store concise, scrubbed notes for one customer in the SQL repository."""

    def __init__(self, repository: CustomerMemoryRepository) -> None:
        self.repository = repository

    async def recall_customer(
        self,
        customer_id: str,
        *,
        limit: int = MAX_RECALL_NOTES,
    ) -> list[CustomerMemory]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        return await self.repository.list_for_customer(
            customer_id,
            limit=min(limit, MAX_RECALL_NOTES),
        )

    async def record_note(
        self,
        *,
        customer_id: str,
        kind: MemoryKind,
        content: str,
        source_ticket_id: str | None = None,
        ticket_body: str | None = None,
        forbidden_values: Sequence[str] = (),
    ) -> CustomerMemory:
        if kind not in ALLOWED_MEMORY_KINDS:
            raise ValueError(f"Unsupported customer-memory kind: {kind}")

        safe_content = scrub(content).strip()
        if not safe_content:
            raise ValueError("Customer-memory content must not be empty")
        if source_ticket_id is not None and ticket_body is None:
            raise ValueError("Ticket-sourced memory requires the source ticket body for filtering")
        if ticket_body and self._is_raw_ticket_text(content, safe_content, ticket_body):
            raise ValueError("Raw ticket text cannot be stored in customer memory")
        if self._contains_forbidden_value(safe_content, forbidden_values):
            raise ValueError("Customer-memory content contains prohibited information")

        existing = await self.repository.find_exact(customer_id, kind, safe_content)
        if existing is not None:
            return existing
        return await self.repository.create(
            customer_id=customer_id,
            source_ticket_id=source_ticket_id,
            kind=kind,
            content=safe_content,
        )

    async def record_resolution(
        self,
        *,
        customer_id: str,
        source_ticket_id: str,
        ticket_body: str,
        summary: str,
        troubleshooting_steps: Sequence[str],
        resolution: str,
        forbidden_values: Sequence[str] = (),
    ) -> list[CustomerMemory]:
        """Record curated outcomes; the ticket body is checked but never stored."""
        candidates = [
            ("past_issue", summary),
            *[("troubleshooting", step) for step in troubleshooting_steps[:3]],
            ("note", resolution),
        ]
        prepared: list[tuple[str, str]] = []
        normalized_body = self._normalize(ticket_body)
        for kind, content in candidates:
            safe_content = scrub(content).strip()
            if not safe_content:
                continue
            if normalized_body and self._is_raw_ticket_text(
                content,
                safe_content,
                ticket_body,
            ):
                raise ValueError("Raw ticket text cannot be stored in customer memory")
            if self._contains_forbidden_value(safe_content, forbidden_values):
                raise ValueError("Customer-memory content contains prohibited information")
            prepared.append((kind, safe_content))

        records: list[CustomerMemory] = []
        for kind, content in prepared:
            records.append(
                await self.record_note(
                    customer_id=customer_id,
                    kind=kind,
                    content=content,
                    source_ticket_id=source_ticket_id,
                    ticket_body=ticket_body,
                    forbidden_values=forbidden_values,
                )
            )
        return records

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    @classmethod
    def _is_raw_ticket_text(cls, content: str, safe_content: str, ticket_body: str) -> bool:
        normalized_body = cls._normalize(ticket_body)
        normalized_original = cls._normalize(content)
        normalized_safe = cls._normalize(safe_content)
        return bool(
            normalized_body
            and (
                normalized_body in normalized_original
                or normalized_body in normalized_safe
                or (
                    len(normalized_safe) >= 100
                    and normalized_safe in normalized_body
                )
            )
        )

    @classmethod
    def _contains_forbidden_value(
        cls,
        content: str,
        forbidden_values: Sequence[str],
    ) -> bool:
        normalized_content = cls._normalize(content)
        return any(
            cls._normalize(value) in normalized_content
            for value in forbidden_values
            if cls._normalize(value)
        )


__all__ = [
    "ALLOWED_MEMORY_KINDS",
    "MAX_RECALL_NOTES",
    "LongTermMemory",
    "MemoryKind",
]
