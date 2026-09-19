"""Domain errors. Raise these instead of returning half-computed results."""

from __future__ import annotations


class FinTwinError(Exception):
    """Base for everything we raise on purpose."""


class InsufficientDataError(FinTwinError):
    """Not enough history/holdings to compute a metric honestly.

    Prefer this over silently returning 0.0 — a wrong number is worse than a
    missing one in a system whose whole selling point is explainability.
    """


class NotImplementedYetError(FinTwinError):
    """Scaffold placeholder. Delete the raise when you implement the function."""


class ToolExecutionError(FinTwinError):
    """A tool the agent selected failed to run."""
