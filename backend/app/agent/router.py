"""Deterministic question router — OWNER: Member 4.

Keyword rules that pick a tool *and* pull its arguments out of the question
("fall 30%" -> shock_pct -0.30, "six months" -> 6). Two jobs:

* the fallback whenever the LLM is unavailable, so the demo never hard-fails;
* the baseline the benchmark compares LLM tool selection against.

It is intentionally simple. Anything it cannot parse it leaves to defaults and
says so in ToolCall.reasoning.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.agent import ToolCall, ToolName
from app.schemas.profile import AssetClass, FinancialProfile

_WORD_NUMBERS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "eighteen": 18,
    "twenty-four": 24,
}
_COUNT = r"(\d+(?:\.\d+)?|" + "|".join(sorted(_WORD_NUMBERS, key=len, reverse=True)) + r")"
_DURATION = re.compile(_COUNT + r"\s*-?\s*(months?|mos?|years?|yrs?)\b")
_RECOVERY = re.compile(
    r"recover\w*\s+(?:in|over|within|after)\s+" + _COUNT + r"\s*(months?|years?|yrs?)\b"
)
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)")
_AMOUNT = re.compile(
    r"(?:(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(k|thousand|lakhs?|l)?\b)"
    r"|(?:\b([\d,]+(?:\.\d+)?)\s*(k|thousand|lakhs?)\b)"
    r"|(?:\b(\d{1,3}(?:,\d{2,3})+|\d{4,})\b)"
)
_SPLIT = re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,2})\b")
_ASSET_WORDS = {
    "debt": AssetClass.DEBT,
    "bond": AssetClass.DEBT,
    "bonds": AssetClass.DEBT,
    "gold": AssetClass.GOLD,
    "cash": AssetClass.CASH,
    "equity": AssetClass.EQUITY,
    "equities": AssetClass.EQUITY,
    "stocks": AssetClass.EQUITY,
}


def _count(token: str) -> float:
    return _WORD_NUMBERS.get(token, None) or float(token)


def parse_duration_months(text: str) -> int | None:
    if "half a year" in text or "half year" in text:
        return 6
    match = _DURATION.search(text)
    if not match:
        return None
    n = _count(match.group(1))
    return round(n * 12) if match.group(2).startswith(("y", "yr")) else round(n)


def parse_percent(text: str) -> float | None:
    match = _PERCENT.search(text)
    return float(match.group(1)) if match else None


def parse_amounts(text: str) -> list[float]:
    """Rupee amounts: '₹20,000', '20k', '1.5 lakh', '25000'. Durations excluded."""
    amounts = []
    for m in _AMOUNT.finditer(text):
        raw = m.group(1) or m.group(3) or m.group(5)
        unit = (m.group(2) or m.group(4) or "").lower()
        value = float(raw.replace(",", ""))
        if unit in ("k", "thousand"):
            value *= 1e3
        elif unit.startswith("l"):
            value *= 1e5
        amounts.append(value)
    return amounts


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


def _scenario_args(q: str, profile: FinancialProfile | None) -> tuple[dict[str, Any], list[str]]:
    """Scenario arguments found in the question, plus notes on what was assumed."""
    args: dict[str, Any] = {}
    notes: list[str] = []
    months = parse_duration_months(q)
    pct = parse_percent(q)
    base_sip = profile.cashflow.monthly_contribution if profile else None

    income = _has(r"\b(income|salary|job|laid off|layoffs?|unemploy\w*|pay ?cut)\b", q)
    income_hit = _has(
        r"\b(lose|lost|losing|stop\w*|drop\w*|cut\w*|fall\w*|reduc\w*"
        r"|zero|halv\w*|half|laid off|without)\b",
        q,
    )
    if income and income_hit:
        if _has(r"\b(halv\w*|half)\b", q):
            args["income_multiplier"] = 0.5
        elif pct is not None and _has(r"\b(drop\w*|cut\w*|fall\w*|reduc\w*)\b", q):
            args["income_multiplier"] = max(0.0, 1 - pct / 100)
        else:
            args["income_multiplier"] = 0.0
        args["income_shock_months"] = months or 6
        if months is None:
            notes.append("no duration given; assumed 6 months")
        return args, notes

    market = _has(r"\b(markets?|nifty|sensex|stocks?|equit\w+|crash\w*|correction|bear)\b", q)
    fall = _has(
        r"\b(crash\w*|fall\w*|fell|drop\w*|declin\w*|tank\w*|correct\w*|plung\w*|down)\b", q
    )
    if market and fall:
        if pct is None:
            pct = 30.0
            notes.append("no size given; assumed a 30% fall")
        args["shock_pct"] = -min(pct, 95.0) / 100
        recovery = _RECOVERY.search(q)
        if recovery:
            n = _count(recovery.group(1))
            args["recovery_months"] = (
                round(n * 12) if recovery.group(2).startswith("y") else round(n)
            )

    sip = _has(r"\b(sips?|invest\w*|contribut\w*|saving)\b", q)
    if sip and _has(r"\b(stop\w*|paus\w*|skip\w*|halt\w*|miss\w*|break)\b", q):
        if months:
            args["pause_months"] = months
        else:
            args["new_monthly_contribution"] = 0.0
            notes.append("no duration given; modeled stopping the SIP for the whole horizon")
    elif sip and _has(
        r"\b(increas\w*|rais\w*|decreas\w*|reduc\w*|lower\w*|cut\w*|chang\w*"
        r"|boost\w*|doubl\w*|halv\w*|top ?up|step ?up|to)\b",
        q,
    ):
        amounts = parse_amounts(q)
        if _has(r"\bdoubl\w*", q) and base_sip is not None:
            args["new_monthly_contribution"] = 2 * base_sip
        elif _has(r"\bhalv\w*", q) and base_sip is not None:
            args["new_monthly_contribution"] = base_sip / 2
        elif amounts:
            amount = amounts[-1]
            if _has(r"\bby\b", q) and base_sip is not None:
                sign = -1 if _has(r"\b(decreas\w*|reduc\w*|lower\w*|cut\w*)\b", q) else 1
                args["new_monthly_contribution"] = max(0.0, base_sip + sign * amount)
            else:
                args["new_monthly_contribution"] = amount

    split = _SPLIT.search(q)
    target = next((a for w, a in _ASSET_WORDS.items() if re.search(rf"\b{w}\b", q)), None)
    if split and _has(r"\b(equity|debt|portfolio|allocation|mix|split)\b", q):
        equity, debt = int(split.group(1)), int(split.group(2))
        if equity + debt == 100:
            args["target_weights"] = {"equity": equity / 100, "debt": debt / 100}
    elif (
        pct is not None
        and target is not None
        and profile is not None
        and profile.holdings
        and _has(r"\b(move|shift|switch|put|allocate|rebalanc\w*)\b", q)
        and "shock_pct" not in args
    ):
        from app.simulation.assumptions import current_weights

        weights = {a.value: w for a, w in current_weights(profile).items()}
        moved = pct / 100
        source = (
            "equity"
            if target != AssetClass.EQUITY
            else max((a for a in weights if a != "equity"), key=lambda a: weights[a], default=None)
        )
        if source and weights.get(source, 0) >= moved:
            weights[source] -= moved
            weights[target.value] = weights.get(target.value, 0) + moved
            args["target_weights"] = {a: round(w, 4) for a, w in weights.items() if w > 1e-9}
        else:
            notes.append(f"could not move {pct:g}% out of {source}; allocation unchanged")

    return args, notes


def select_tools(question: str, profile: FinancialProfile | None = None) -> list[ToolCall]:
    """Pick the tool(s) and arguments for `question` with keyword rules."""
    q = question.lower().strip()
    hypothetical = _has(
        r"\b(what if|what happens|what would|suppose|imagine|if i|if my|if the|if markets?)\b", q
    )

    # "15k vs 20k SIP" -> several alternatives side by side.
    amounts = parse_amounts(q)
    if (
        _has(r"\b(vs\.?|versus|compare|or)\b", q)
        and len(amounts) >= 2
        and _has(r"\b(sips?|invest\w*)\b", q)
    ):
        scenarios = [{"new_monthly_contribution": a} for a in amounts[:5]]
        return [
            ToolCall(
                tool=ToolName.COMPARE_SCENARIOS,
                arguments={"scenarios": scenarios},
                reasoning="several SIP amounts to compare",
            )
        ]

    args, notes = _scenario_args(q, profile)
    if args or (hypothetical and _has(r"\b(crash|fall|drop|stop|pause|income|job|sip)\b", q)):
        reasoning = "hypothetical / scenario question"
        if notes:
            reasoning += " (" + "; ".join(notes) + ")"
        return [ToolCall(tool=ToolName.RUN_SCENARIO, arguments=args, reasoning=reasoning)]

    if _has(
        r"\b(goals?|on track|reach|target|enough|how much should i (?:invest|save)|retire\w*)\b", q
    ):
        return [ToolCall(tool=ToolName.PROJECT_GOAL, reasoning="goal progress question")]

    if _has(r"\b(health|how am i doing|score|worry|financial position|overall)\b", q):
        return [ToolCall(tool=ToolName.COMPUTE_HEALTH_SCORE, reasoning="overall health question")]

    if _has(r"\b(volatil\w*|forecast)\b", q):
        symbol = re.search(r"\b([A-Z][A-Z0-9&]{2,19})\b", question)
        return [
            ToolCall(
                tool=ToolName.FORECAST_VOLATILITY,
                arguments={"symbol": symbol.group(1) if symbol else "NIFTYBEES"},
                reasoning="volatility question",
            )
        ]

    if _has(
        r"^(what is|what's|what are|what does|explain|why|how does|how do"
        r"|define|tell me about|meaning of)\b",
        q,
    ) and not _has(r"\b(my|i)\b", q):
        return [
            ToolCall(
                tool=ToolName.RESEARCH_MARKET,
                arguments={"query": question},
                reasoning="concept / background question",
            )
        ]

    return [ToolCall(tool=ToolName.ANALYZE_PORTFOLIO, reasoning="portfolio question (default)")]
