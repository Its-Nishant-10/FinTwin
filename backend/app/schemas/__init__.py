"""Shared API contracts.

Every module in FinTwin speaks these types. They are the seam that lets six
people build in parallel: agree on the shape here first, then implement behind it.

CHANGING A SCHEMA IS A BREAKING CHANGE. Open a PR, tag everyone whose module
consumes it, and announce it in the team channel before merging.
"""

from app.schemas.agent import (
    AgentRequest,
    AgentResponse,
    ToolCall,
    ToolName,
    ToolResult,
)
from app.schemas.common import Assumptions, Evidence, Explanation, Money, Percentile
from app.schemas.portfolio import (
    AllocationSlice,
    ConcentrationMetrics,
    PortfolioMetrics,
    RiskMetrics,
)
from app.schemas.profile import (
    Cashflow,
    FinancialProfile,
    Goal,
    Holding,
    Liability,
    RiskConstraints,
)
from app.schemas.scenario import (
    AllocationChangeParams,
    ContributionChangeParams,
    IncomeShockParams,
    MarketStressParams,
    ScenarioComparison,
    ScenarioRequest,
    ScenarioResult,
    ScenarioType,
    SimulationSettings,
)

__all__ = [
    "Assumptions",
    "Evidence",
    "Explanation",
    "Money",
    "Percentile",
    "Cashflow",
    "FinancialProfile",
    "Goal",
    "Holding",
    "Liability",
    "RiskConstraints",
    "AllocationSlice",
    "ConcentrationMetrics",
    "PortfolioMetrics",
    "RiskMetrics",
    "AllocationChangeParams",
    "ContributionChangeParams",
    "IncomeShockParams",
    "MarketStressParams",
    "ScenarioComparison",
    "ScenarioRequest",
    "ScenarioResult",
    "ScenarioType",
    "SimulationSettings",
    "AgentRequest",
    "AgentResponse",
    "ToolCall",
    "ToolName",
    "ToolResult",
]
