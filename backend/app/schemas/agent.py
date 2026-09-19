"""Agent orchestration contracts (Member 4).

The division of labour, which is the whole architectural point of the project:

    LLM       -> understand the question, pick tools, explain the output
    Tools     -> do the arithmetic
    Retrieval -> supply evidence

The LLM never computes a number that reaches the user.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import Evidence, Explanation
from app.schemas.profile import FinancialProfile


class ToolName(str, Enum):
    """The registry. Adding a tool means adding it here first.

    The benchmark (Member 6) scores tool-selection accuracy against these names,
    so keep them stable once the eval set is written.
    """

    ANALYZE_PORTFOLIO = "analyze_portfolio"
    COMPUTE_HEALTH_SCORE = "compute_health_score"
    RUN_SCENARIO = "run_scenario"
    COMPARE_SCENARIOS = "compare_scenarios"
    PROJECT_GOAL = "project_goal"
    EXTRACT_DOCUMENT = "extract_document"
    RESEARCH_MARKET = "research_market"
    FORECAST_VOLATILITY = "forecast_volatility"


class ToolCall(BaseModel):
    tool: ToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    reasoning: str | None = Field(default=None, description="Why the agent picked this tool")


class ToolResult(BaseModel):
    tool: ToolName
    ok: bool = True
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    latency_ms: float | None = None


class AgentRequest(BaseModel):
    question: str = Field(
        ..., min_length=1, description="e.g. 'What if I stop my SIP for 6 months?'"
    )
    profile: FinancialProfile | None = None
    conversation_id: str | None = None


class AgentResponse(BaseModel):
    answer: Explanation
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    latency_ms: float | None = None


class ExtractedField(BaseModel):
    """Document extraction always goes through user confirmation before use."""

    field: str
    value: Any
    confidence: float = Field(..., ge=0, le=1)
    source_page: int | None = None
    needs_confirmation: bool = True


class DocumentExtraction(BaseModel):
    filename: str
    doc_type: str = Field(default="unknown", description="e.g. 'cas_statement', 'bank_statement'")
    fields: list[ExtractedField] = Field(default_factory=list)
    proposed_profile: FinancialProfile | None = None
    warnings: list[str] = Field(default_factory=list)


class ConfirmExtractionRequest(BaseModel):
    """The user's reviewed extraction, applied onto their current profile.

    Only fields the user confirmed (needs_confirmation=False) are applied; the
    rest are ignored. The UI flips the flag when the user ticks a field, and may
    edit `value` first.
    """

    profile: FinancialProfile
    fields: list[ExtractedField]
