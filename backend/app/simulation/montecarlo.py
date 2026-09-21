"""Monte Carlo path generation — OWNER: Member 5.

Log-normal monthly returns with monthly contributions, plus two optional
refinements over plain geometric Brownian motion:

* ``return_model="student_t"`` — fat-tailed monthly shocks. Normal returns
  understate how often markets fall hard in a single month; a Student-t with
  the same volatility puts more weight in the tails.
* ``recovery_months`` — after a market shock, a deterministic recovery that
  restores the lost level over N months (a "V-shaped" recovery). Without it a
  shock is a permanent level loss, which is the more pessimistic reading.

Paths depend only on (seed, n_paths, horizon_months, return_model, t_df).
That is deliberate: two runs with the same seed see the same random market, so
the difference between them is caused by the inputs alone (common random
numbers). The Goal Failure Analysis in engine.py relies on this.
"""

from __future__ import annotations

import numpy as np

# Student-t shocks are truncated here, in standard deviations. A t distribution
# has no finite moment-generating function, so an untruncated draw can produce
# an absurd one-month gain; 6 sd is far beyond anything the tails need.
_T_CLIP_SD = 6.0


def standard_shocks(
    n_paths: int,
    horizon_months: int,
    seed: int | None,
    return_model: str = "gbm",
    t_df: float = 5.0,
) -> np.ndarray:
    """Unit-variance random shocks, shape (n_paths, horizon_months)."""
    rng = np.random.default_rng(seed)
    size = (n_paths, horizon_months)
    if return_model == "gbm":
        return rng.standard_normal(size)
    if return_model == "student_t":
        if t_df <= 2:
            raise ValueError("t_df must be > 2 for the variance to exist")
        z = rng.standard_t(t_df, size) / np.sqrt(t_df / (t_df - 2))
        return np.clip(z, -_T_CLIP_SD, _T_CLIP_SD)
    raise ValueError(f"unknown return_model: {return_model!r}")


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
    recovery_months: int | None = None,
    return_model: str = "gbm",
    t_df: float = 5.0,
) -> np.ndarray:
    """Return an (n_paths, horizon_months + 1) array of portfolio values.

    Contributions are added at the start of each month, then the balance is
    grown by that month's random return. `contribution_schedule` (length
    horizon_months) overrides the flat contribution — that is how SIP pauses and
    income shocks are expressed.

    A `shock_pct` of -0.30 knocks 30% off the balance at the end of
    `shock_at_month`, on top of the random path, which is what "what if markets
    fall 30%" means here. With `recovery_months`, the lost level is regained
    evenly over the following months; money contributed during the recovery
    benefits from it, exactly as buying after a real crash does.
    """
    monthly_mu = expected_annual_return / 12
    monthly_sigma = annual_volatility / np.sqrt(12)

    if contribution_schedule is None:
        contribution_schedule = np.full(horizon_months, monthly_contribution, dtype=float)
    if len(contribution_schedule) != horizon_months:
        raise ValueError("contribution_schedule must have exactly horizon_months entries")
    if not -1.0 < shock_pct <= 0.0:
        raise ValueError("shock_pct must be in (-1, 0]")

    # Drift is set so the expected simple monthly return is exactly monthly_mu:
    # E[exp(X)] = 1 + monthly_mu. Using log1p here (rather than monthly_mu
    # directly) is what makes a zero-volatility run reproduce plain
    # deterministic compounding, which the tests pin down — a user comparing us
    # against a SIP calculator must see the same number.
    drift = np.log1p(monthly_mu) - 0.5 * monthly_sigma**2
    shocks = standard_shocks(n_paths, horizon_months, seed, return_model, t_df)
    monthly_returns = np.exp(drift + monthly_sigma * shocks)

    recovery = np.ones(horizon_months)
    if shock_pct and recovery_months:
        per_month = (1 + shock_pct) ** (-1 / recovery_months)
        start = shock_at_month + 1
        recovery[start : start + recovery_months] = per_month

    values = np.empty((n_paths, horizon_months + 1), dtype=float)
    values[:, 0] = initial_value

    for month in range(horizon_months):
        balance = (values[:, month] + contribution_schedule[month]) * monthly_returns[:, month]
        if shock_pct and month == shock_at_month:
            balance = balance * (1 + shock_pct)
        values[:, month + 1] = balance * recovery[month]

    return values


def summarize(paths: np.ndarray, percentiles: list[float]) -> dict[float, float]:
    """Terminal-value percentiles."""
    terminal = paths[:, -1]
    return {p: float(np.percentile(terminal, p)) for p in percentiles}


def path_percentiles(paths: np.ndarray, percentiles: list[float]) -> dict[float, np.ndarray]:
    """Percentiles of portfolio value at every month: one (horizon_months + 1) array each."""
    if not percentiles:
        return {}
    values = np.percentile(paths, percentiles, axis=0)
    return {p: values[i] for i, p in enumerate(percentiles)}


def success_probability(paths: np.ndarray, target: float, month: int | None = None) -> float:
    """Share of paths at or above the target at `month` (default: the last month)."""
    column = paths[:, -1] if month is None else paths[:, month]
    return float((column >= target).mean())
