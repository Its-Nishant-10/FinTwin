"""Digital-twin CRUD.  OWNER: Member 2 (Data/Backend)."""

from __future__ import annotations

from fastapi import APIRouter

from app.data.repository import ProfileRepository
from app.data.sample import load_sample_profile
from app.schemas import FinancialProfile

router = APIRouter(prefix="/profile", tags=["profile"])
_repo = ProfileRepository()


@router.get("/sample", response_model=FinancialProfile)
def get_sample_profile() -> FinancialProfile:
    """The demo twin from the proposal: 3L invested, 15k/month, 20L in 5 years.

    Every other module can develop against this without waiting for the DB.
    """
    return load_sample_profile()


@router.get("/{user_id}", response_model=FinancialProfile)
def get_profile(user_id: str) -> FinancialProfile:
    return _repo.get(user_id)


@router.put("/{user_id}", response_model=FinancialProfile)
def upsert_profile(user_id: str, profile: FinancialProfile) -> FinancialProfile:
    return _repo.upsert(user_id, profile)
