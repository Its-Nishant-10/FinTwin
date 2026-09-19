"""Number grounding — OWNER: Member 4.

The project's one hard rule is that the LLM never produces a number that
reaches the user. This module enforces it after the fact: every figure in the
model's prose must match a figure some tool actually returned (or that the user
supplied), within the precision the prose displays it at. "₹16.7 lakh" must be
within ₹5,000 of a real number; "₹17 lakh" within ₹50,000.

It is a heuristic guard, not a proof. It catches invented and mis-copied
figures; it cannot tell whether a *correct* number was attached to the wrong
label. The benchmark should report how often it fires.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any

_UNITS = {
    "lakh": 1e5,
    "lakhs": 1e5,
    "lac": 1e5,
    "lacs": 1e5,
    "l": 1e5,
    "crore": 1e7,
    "crores": 1e7,
    "cr": 1e7,
    "k": 1e3,
    "thousand": 1e3,
}

_NUMBER = re.compile(
    r"""
    (?<![\w.])                                  # not glued to a word, e.g. 'p10'
    (?P<currency>₹\s?|rs\.?\s?|inr\s?)?
    (?P<num>\d[\d,]*(?:\.\d+)?)
    (?![\d,])
    \s?
    (?P<unit>%|percent\b|lakhs?\b|lacs?\b|crores?\b|cr\b|thousand\b|k\b|l\b)?
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ------------------------------------------------------------------ formatting


def _indian_grouping(n: int) -> str:
    """1234567 -> '12,34,567'."""
    s = str(abs(n))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def format_inr(value: float) -> str:
    """Rupees the way an Indian reader expects them: ₹15,000 · ₹16.7 lakh · ₹1.25 crore."""
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1e7:
        return f"{sign}₹{v / 1e7:.2f}".rstrip("0").rstrip(".") + " crore"
    if v >= 1e5:
        return f"{sign}₹{v / 1e5:.1f}".removesuffix(".0") + " lakh"
    return f"{sign}₹{_indian_grouping(round(v))}"


def format_pct(fraction: float) -> str:
    return f"{fraction * 100:.0f}%"


# ------------------------------------------------------------------- grounding


def _leaves(obj: Any) -> Iterable[float]:
    """Numeric leaves, including figures written inside tool-produced strings
    (a label like "SIP changed to ₹20,000" or a sourced research passage)."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, int | float):
        if math.isfinite(obj):
            yield float(obj)
    elif isinstance(obj, str):
        for _written, value, _tol in claimed_numbers(obj):
            yield value
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _leaves(value)
    elif isinstance(obj, list | tuple):
        for value in obj:
            yield from _leaves(value)


def grounded_values(*sources: Any) -> set[float]:
    """Every number a sentence may legitimately quote, with its natural restatements.

    A fraction may be quoted as a percentage (0.32 -> 32%) and a whole month
    count as years (60 -> 5) or the reverse. Those restatements are applied only
    where they make sense; applying them to rupee amounts would let invented
    figures match by coincidence.
    """
    values: set[float] = set()
    for source in sources:
        for x in _leaves(source):
            x = abs(x)
            values.add(x)
            if x <= 1:
                values.add(x * 100)
            if x <= 600 and x == int(x):
                values.update({x / 12, x * 12})
    return values


def _tolerance(value: float, text: str, scale: float) -> float:
    """Half a unit in the last place the text shows, capped at 5% and floored at 0.5%."""
    if "." in text:
        decimals = len(text.split(".")[1])
        place = 10.0 ** (-decimals) * scale
    else:
        digits = text.replace(",", "")
        trailing_zeros = len(digits) - len(digits.rstrip("0"))
        place = 10.0**trailing_zeros * scale
    return max(min(place / 2, 0.05 * value), 0.005 * value, 1e-9)


def claimed_numbers(text: str) -> list[tuple[str, float, float]]:
    """(as written, value, tolerance) for every figure worth checking in `text`."""
    claims = []
    for match in _NUMBER.finditer(text):
        raw = match.group("num")
        unit = (match.group("unit") or "").lower()
        has_currency = bool(match.group("currency"))
        value = float(raw.replace(",", ""))

        # Small counts ("6 months", "3 scenarios") and calendar years are not
        # financial claims.
        if not unit and not has_currency:
            if value <= 12 or (1900 <= value <= 2100 and "." not in raw):
                continue

        scale = _UNITS.get(unit, 1.0)
        value *= scale
        claims.append((match.group(0).strip(), value, _tolerance(value, raw, scale)))
    return claims


def unverified_numbers(text: str, grounded: set[float]) -> list[str]:
    """Figures in `text` that no grounded value supports."""
    return [
        written
        for written, value, tol in claimed_numbers(text)
        if not any(abs(value - g) <= tol for g in grounded)
    ]
