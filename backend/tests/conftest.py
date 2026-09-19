"""Shared fixtures. Add yours here rather than duplicating setup per file."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.data.sample import load_sample_profile
from app.main import app
from app.schemas.profile import FinancialProfile


@pytest.fixture
def profile() -> FinancialProfile:
    return load_sample_profile()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
