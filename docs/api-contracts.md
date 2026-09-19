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
| POST | `/portfolio/analyze` | `FinancialProfile` → `PortfolioMetrics` | 1 | 🟡 allocation + concentration done |
| POST | `/portfolio/health-score` | `FinancialProfile` → `HealthScore` | 1 | 🟡 liquidity only |
| POST | `/scenario/run` | `ScenarioRequest` → `ScenarioResult` | 5 | 🟡 baseline + stress done |
| POST | `/scenario/compare` | `ScenarioRequest[]` → `ScenarioComparison` | 5 | ✅ |
| POST | `/agent/ask` | `AgentRequest` → `AgentResponse` | 4 | 🟡 keyword routing, no LLM |
| GET | `/agent/tools` | → tool registry | 4 | ✅ |
| POST | `/documents/extract` | multipart → `DocumentExtraction` | 4 | ⬜ stub |

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
```

### `ScenarioResult`
```
scenario_type, label
assumptions           ← must always be populated
terminal_percentiles  [ {p, value} ]
median_path           [ value per month, length horizon_months + 1 ]
total_contributed
goal_outcomes         [ {goal_name, target_amount, success_probability, median_shortfall} ]
cash_runway_months
explanation
```

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
