"""OWNER: Member 4. The guard that keeps model-invented numbers away from users."""

from __future__ import annotations

import pytest

from app.agent.grounding import format_inr, grounded_values, unverified_numbers

TOOL_OUTPUT = {
    "median": 1_669_267,
    "success_probability": 0.32,
    "horizon_months": 60,
    "required": 16_204,
    "target": 2_000_000,
    "label": "SIP changed to ₹20,000",
}
GROUNDED = grounded_values(TOOL_OUTPUT)


@pytest.mark.parametrize(
    "text",
    [
        "The median is ₹16.7 lakh.",  # reformatted to one decimal
        "roughly ₹17 lakh",  # rounded to what the text displays
        "₹16,204 a month",
        "a 32% chance",  # fraction shown as a percentage
        "over 5 years",  # 60 months shown as years
        "your ₹20,00,000 target",  # Indian digit grouping
        "a SIP of ₹20,000",  # figure inside a tool-produced string
        "in 2026, over 3 scenarios",  # years and small counts are not claims
    ],
)
def test_faithful_restatements_pass(text):
    assert unverified_numbers(text, GROUNDED) == []


@pytest.mark.parametrize(
    ("text", "flagged"),
    [
        ("The median is ₹18.2 lakh.", "₹18.2 lakh"),
        ("a 45% chance", "45%"),
        ("₹1,66,926 per month", "₹1,66,926"),  # near target/12, must not match by coincidence
        ("you'd end with ₹1.2 crore", "₹1.2 crore"),
    ],
)
def test_invented_figures_are_flagged(text, flagged):
    assert unverified_numbers(text, GROUNDED) == [flagged]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (15_000, "₹15,000"),
        (94_175, "₹94,175"),
        (1_669_267, "₹16.7 lakh"),
        (2_000_000, "₹20 lakh"),
        (12_345_678, "₹1.23 crore"),
        (-540_000, "-₹5.4 lakh"),
    ],
)
def test_format_inr(value, expected):
    assert format_inr(value) == expected
