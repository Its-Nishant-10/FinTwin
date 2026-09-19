"""Natural-language what-if chat.  OWNER: Member 4 (Agent/LLM)."""

from __future__ import annotations

from fastapi import APIRouter

from app.agent import orchestrator
from app.schemas import AgentRequest, AgentResponse

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/ask", response_model=AgentResponse)
def ask(request: AgentRequest) -> AgentResponse:
    """Route a question to the right tools, then explain what the tools returned."""
    return orchestrator.answer(request)


@router.get("/tools")
def list_tools() -> dict[str, list[dict[str, str]]]:
    """The tool registry, as the LLM sees it. Useful for debugging tool selection."""
    return {"tools": orchestrator.describe_tools()}
