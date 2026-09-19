"""Profile persistence — OWNER: Member 2.

Ships with an in-memory store so the API is usable on day 1. Swap the internals
for PostgreSQL without changing the method signatures, and everyone else's code
keeps working.
"""

from __future__ import annotations

from app.data.sample import load_sample_profile
from app.schemas.profile import FinancialProfile


class ProfileRepository:
    """TODO(member-2): back this with SQLAlchemy + PostgreSQL (see app/data/models.py)."""

    def __init__(self) -> None:
        self._store: dict[str, FinancialProfile] = {"demo-user": load_sample_profile()}

    def get(self, user_id: str) -> FinancialProfile:
        profile = self._store.get(user_id)
        if profile is None:
            # Until auth exists, an unknown user gets a fresh empty twin.
            profile = FinancialProfile(user_id=user_id)
            self._store[user_id] = profile
        return profile

    def upsert(self, user_id: str, profile: FinancialProfile) -> FinancialProfile:
        profile.user_id = user_id
        self._store[user_id] = profile
        return profile

    def delete(self, user_id: str) -> None:
        self._store.pop(user_id, None)
