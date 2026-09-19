"""A scripted stand-in for the Anthropic client, so the LLM path is testable offline."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def tool_use(name: str, arguments: dict[str, Any], block_id: str = "toolu_1") -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", name=name, input=arguments, id=block_id)


def response(*blocks: SimpleNamespace, stop_reason: str | None = None) -> SimpleNamespace:
    if stop_reason is None:
        stop_reason = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


class ScriptedLLM:
    """Returns the queued responses in order and records every request."""

    def __init__(self, *responses: SimpleNamespace) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        return self.responses.pop(0)


def install(monkeypatch, scripted: ScriptedLLM) -> ScriptedLLM:
    from app.agent import llm

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "create", scripted)
    return scripted
