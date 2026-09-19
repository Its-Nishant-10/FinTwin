from __future__ import annotations

from fastapi import APIRouter

from app import __version__

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. The frontend pings this on load."""
    return {"status": "ok", "version": __version__}
