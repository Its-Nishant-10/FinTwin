"""Primitives shared across every layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# All monetary amounts in FinTwin are INR, stored as a float of whole rupees.
# Do not mix currencies without extending this type first.
Money = float


class Percentile(BaseModel):
    """One point on an outcome distribution."""

    p: float = Field(..., ge=0, le=100, description="Percentile, e.g. 10, 50, 90")
    value: Money


class PercentilePath(BaseModel):
    """One percentile of the outcome distribution, followed month by month.

    Several of these make the p10-p90 band the UI shades around the median, so a
    distribution is never drawn as a single line that reads like a prediction.
    """

    p: float = Field(..., ge=0, le=100, description="Percentile, e.g. 10, 50, 90")
    values: list[Money] = Field(..., description="Value at every month, month 0 first")


class Assumptions(BaseModel):
    """Every simulated number must carry the assumptions that produced it.

    This model backs the 'Assumption Transparency Panel' in the UI. If a result
    can't name its assumptions, it should not be shown to the user.
    """

    horizon_months: int = Field(..., gt=0)
    expected_annual_return: float = Field(..., description="Decimal, e.g. 0.12 for 12%")
    annual_volatility: float = Field(..., description="Decimal, e.g. 0.18 for 18%")
    monthly_contribution: Money = 0.0
    inflation: float = 0.0
    n_paths: int = Field(default=10_000, gt=0)
    seed: int | None = Field(default=None, description="Set for reproducible runs")
    notes: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    """A traceable source behind a claim (Member 4 / RAG layer)."""

    claim: str
    source: str = Field(..., description="URL, document name, or tool identifier")
    snippet: str | None = None
    retrieved_at: datetime | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class Explanation(BaseModel):
    """Plain-language answer plus the machinery that justifies it.

    The LLM writes `summary`. It does NOT invent `numbers` — those come from
    deterministic tools and are passed through untouched.
    """

    summary: str
    assumptions: Assumptions | None = None
    numbers: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
