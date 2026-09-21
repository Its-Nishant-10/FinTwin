# API contracts

Live, always-correct version: **http://localhost:8000/docs** (run `make backend`).

Every request and response below is a Pydantic model in `backend/app/schemas/`.
The TypeScript mirrors live in `frontend/lib/types.ts` and must be updated in the
same PR as any schema change.

## Endpoints

| Method | Path | Body → Response | Owner | Status |
|---|---|---|---|---|
| GET | `/health` | → `{status, version}` | — | ✅ |
| GET | `/profile/sample` | → `FinancialProfile` | 2 | ✅ |
| GET | `/profile/{user_id}` | → `FinancialProfile` | 2 | ✅ in-memory |
| PUT | `/profile/{user_id}` | `FinancialProfile` → `FinancialProfile` | 2 | ✅ in-memory |
| POST | `/portfolio/analyze` | `FinancialProfile` → `PortfolioMetrics` | 1 | 🟡 allocation + concentration done; risk metrics and correlation are `null`/`{}` until price history is wired in |
| POST | `/portfolio/health-score` | `FinancialProfile` → `HealthScore` | 1 | ✅ all five dimensions; one that can't be scored honestly (e.g. no income) is `null`, `overall` averages the scored ones |
| POST | `/scenario/run` | `ScenarioRequest` → `ScenarioResult` | 5 | ✅ |
| POST | `/scenario/whatif` | `ScenarioRequest` → `ScenarioComparison` (auto baseline) | 5 | ✅ |
| POST | `/scenario/compare` | `ScenarioRequest[]` → `ScenarioComparison` | 5 | ✅ |
| POST | `/agent/ask` | `AgentRequest` → `AgentResponse` | 4 | ✅ LLM + deterministic fallback |
| GET | `/agent/tools` | → tool registry | 4 | ✅ |
| POST | `/documents/extract` | multipart (PDF/CSV/text) → `DocumentExtraction` | 4 | ✅ |
| POST | `/documents/confirm` | `ConfirmExtractionRequest` → `FinancialProfile` | 4 | ✅ |

Scenario errors come back as `422` with a readable `detail` (e.g. a `market_stress`
scenario without `market_stress` params); parts that aren't built yet return `501`.

## Core types

### `FinancialProfile` — the digital twin
```
user_id, as_of
cashflow   { monthly_income, monthly_expenses, monthly_contribution }
holdings   [ { symbol, asset_class, sector, quantity, avg_cost, current_price } ]
cash_balance, other_assets
liabilities[ { name, outstanding, monthly_emi, annual_rate } ]
goals      [ { name, target_amount, horizon_months, priority } ]
risk       { risk_tolerance, max_equity_pct, max_single_holding_pct, min_emergency_months }
```
Computed properties: `portfolio_value`, `total_liabilities`, `net_worth`.

### `ScenarioRequest`
```
profile, scenario_type, horizon_months
expected_annual_return, annual_volatility
settings { n_paths, seed, percentiles }
market_stress        { shock_pct, shock_at_month, recovery_months }
income_shock         { income_multiplier, duration_months, start_month }
contribution_change  { new_monthly_contribution, pause_months, pause_start_month }
allocation_change    { target_weights: {asset_class: weight} }   ← weights sum to 1
settings.return_model  "gbm" | "student_t"   (+ t_df)
```

Perturbations apply whenever their params are present, so one request can combine a
crash with a SIP pause. `scenario_type` must match: a `market_stress` type without
`market_stress` params is rejected. For allocation changes, return and volatility on
both sides are derived from `app/simulation/assumptions.py`; the request's
`expected_annual_return` / `annual_volatility` are ignored.

### `ScenarioResult`
```
scenario_type, label
assumptions           ← must always be populated
terminal_percentiles  [ {p, value} ]
median_path           [ value per month, length horizon_months + 1 ]
percentile_paths      [ {p, values: [value per month]} ]   ← one per settings.percentiles;
                        the UI shades the outermost pair (p10–p90) around the median
total_contributed
goal_outcomes         [ {goal_name, target_amount, success_probability, median_shortfall,
                          evaluated_at_month, shortfall_drivers, required_monthly_contribution} ]
cash_runway_months
explanation
```

### Goal Failure Analysis (`shortfall_drivers`)

Additive: the values sum exactly to `target − median outcome` (negative means a
cushion). `baseline_plan` is the gap with no perturbation applied; each other key
(`market_shock`, `contribution_change`, `income_shock`, `allocation_change`) is that
perturbation's Shapley share, computed by re-running the simulation with each
combination switched on and off against the same random market. Positive widens the
shortfall, negative narrows it. `required_monthly_contribution` is the flat,
uninterrupted SIP at which the median outcome reaches the target under the scenario's
market conditions.

Each goal is scored at its own `horizon_months`; goals beyond the simulation horizon
are skipped and named in `assumptions.notes`.

## Conventions

- **Currency:** INR, plain floats of whole rupees. No mixed currencies.
- **Rates:** decimals, not percentages. `0.12` is 12%.
- **Shocks:** negative decimals. `-0.30` is a 30% fall.
- **Time:** months everywhere. Month 0 is today.
- **Unknown metrics:** `null`, never `0.0`.
- **Errors:** `4xx` with `{detail}`; a failed *tool* returns `ToolResult(ok=false)` rather
  than failing the whole request.

## Example

```bash
curl -s localhost:8000/profile/sample > profile.json

curl -s -X POST localhost:8000/scenario/run \
  -H 'Content-Type: application/json' \
  -d "{\"profile\": $(cat profile.json),
       \"scenario_type\": \"market_stress\",
       \"horizon_months\": 60,
       \"market_stress\": {\"shock_pct\": -0.30, \"shock_at_month\": 0},
       \"settings\": {\"n_paths\": 5000, \"seed\": 42}}" | python3 -m json.tool
```
