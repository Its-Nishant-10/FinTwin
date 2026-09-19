"""Shared fixtures. Add yours here rather than duplicating setup per file."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.data.sample import load_sample_profile
from app.main import app
from app.schemas.profile import FinancialProfile


@pytest.fixture(autouse=True)
def _no_real_llm(monkeypatch):
    """Never call the paid API from tests, even if a developer's .env has a key.

    Tests that exercise the LLM path patch llm.available/llm.create themselves.
    """
    from app.agent import llm

    monkeypatch.setattr(llm, "available", lambda: False)


@pytest.fixture
def profile() -> FinancialProfile:
    return load_sample_profile()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
