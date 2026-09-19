"""Monte Carlo path generation — OWNER: Member 5.

Working geometric-Brownian-motion baseline with monthly contributions. It is
deliberately simple: get the plumbing right first, then make the return model
more honest (fat tails, regime-conditioned vol from Member 3, block bootstrap
from real history).
"""

from __future__ import annotations

import numpy as np


def simulate_paths(
    initial_value: float,
    monthly_contribution: float,
    horizon_months: int,
    expected_annual_return: float,
    annual_volatility: float,
    n_paths: int = 10_000,
    seed: int | None = 42,
    contribution_schedule: np.ndarray | None = None,
    shock_pct: float = 0.0,
    shock_at_month: int = 0,
) -> np.ndarray:
    """Return an (n_paths, horizon_months + 1) array of portfolio values.

    Contributions are added at the start of each month, then the balance is
    grown by that month's random return. `contribution_schedule` (length
    horizon_months) overrides the flat contribution — that is how SIP pauses and
    income shocks are expressed.

    A `shock_pct` of -0.30 knocks 30% off the balance at `shock_at_month`, on
    top of the random path, which is what "what if markets fall 30%" means here.
    """
    rng = np.random.default_rng(seed)

    monthly_mu = expected_annual_return / 12
    monthly_sigma = annual_volatility / np.sqrt(12)

    if contribution_schedule is None:
        contribution_schedule = np.full(horizon_months, monthly_contribution, dtype=float)
    if len(contribution_schedule) != horizon_months:
        raise ValueError("contribution_schedule must have exactly horizon_months entries")

    # Log-normal monthly returns. The drift is set so that the expected simple
    # return is exactly monthly_mu: E[exp(X)] = 1 + monthly_mu. Using log1p here
    # (rather than monthly_mu directly) is what makes a zero-volatility run
    # reproduce plain deterministic compounding, which the tests pin down --
    # a user comparing us against a SIP calculator must see the same number.
    drift = np.log1p(monthly_mu) - 0.5 * monthly_sigma**2
    shocks = rng.normal(drift, monthly_sigma, size=(n_paths, horizon_months))
    monthly_returns = np.exp(shocks)

    values = np.empty((n_paths, horizon_months + 1), dtype=float)
    values[:, 0] = initial_value

    for month in range(horizon_months):
        balance = values[:, month] + contribution_schedule[month]
        balance = balance * monthly_returns[:, month]
        if shock_pct and month == shock_at_month:
            balance = balance * (1 + shock_pct)
        values[:, month + 1] = balance

    return values


def summarize(paths: np.ndarray, percentiles: list[float]) -> dict[float, float]:
    """Terminal-value percentiles."""
    terminal = paths[:, -1]
    return {p: float(np.percentile(terminal, p)) for p in percentiles}


def success_probability(paths: np.ndarray, target: float) -> float:
    """Share of paths whose terminal value clears the target."""
    return float((paths[:, -1] >= target).mean())
