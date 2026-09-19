"""Document-to-Portfolio — OWNER: Member 4.

Extracted values are proposals, not facts. They go back to the user for
confirmation before they ever touch a profile.
"""

from __future__ import annotations

from app.schemas.agent import DocumentExtraction


def extract(filename: str, content: bytes) -> DocumentExtraction:
    """Pull holdings, balances and cashflows out of a statement.

    TODO(member-4): PDF text extraction (pdfplumber) -> LLM structured output ->
    ExtractedField list with per-field confidence. Set needs_confirmation=True
    on everything; Member 6's UI renders the confirmation step.
    """
    return DocumentExtraction(
        filename=filename,
        doc_type="unknown",
        fields=[],
        warnings=["Extraction not implemented yet — see app/agent/extraction.py"],
    )
