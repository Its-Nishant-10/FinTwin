"""Retrieval + evidence tracking — OWNER: Member 4.

A claim without a source does not ship. Every summary sentence should map to an
Evidence entry the UI can display.
"""

from __future__ import annotations

from app.core.errors import NotImplementedYetError
from app.schemas.common import Evidence


def research(query: str, k: int = 5) -> list[Evidence]:
    """TODO(member-4): vector search over an ingested corpus, return sourced snippets."""
    raise NotImplementedYetError("research.research")
