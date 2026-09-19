"""Document-to-Portfolio extraction.  OWNER: Member 4 (Agent/LLM).

Two steps, on purpose:
  POST /documents/extract  -> proposed fields, all awaiting confirmation
  POST /documents/confirm  -> apply only the fields the user confirmed
Extracted values never reach a profile without passing through step two.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import ValidationError

from app.agent import extraction
from app.schemas.agent import ConfirmExtractionRequest, DocumentExtraction
from app.schemas.profile import FinancialProfile

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/extract", response_model=DocumentExtraction)
async def extract_document(file: UploadFile = File(...)) -> DocumentExtraction:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File larger than 10 MB")
    return extraction.extract(filename=file.filename or "upload", content=content)


@router.post("/confirm", response_model=FinancialProfile)
def confirm_extraction(request: ConfirmExtractionRequest) -> FinancialProfile:
    """Return the profile with the user-confirmed fields applied. Does not save it."""
    try:
        return extraction.apply_confirmed(request.profile, request.fields)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
