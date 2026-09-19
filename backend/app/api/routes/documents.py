"""Document-to-Portfolio extraction.  OWNER: Member 4 (Agent/LLM).

Extracted values are always returned for user confirmation — they are never
written into a profile automatically.
"""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.agent import extraction
from app.schemas.agent import DocumentExtraction

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/extract", response_model=DocumentExtraction)
async def extract_document(file: UploadFile = File(...)) -> DocumentExtraction:
    content = await file.read()
    return extraction.extract(filename=file.filename or "upload", content=content)
