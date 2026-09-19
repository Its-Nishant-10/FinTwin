# Team, ownership and day-by-day tasks

## Day 1 — everyone, before anything else

```bash
git clone <repo-url> && cd FinTwin
cp .env.example .env
make setup
make check          # 26 tests must pass
make backend        # then open http://localhost:8000/docs
```

Then claim your package below, make one small commit in it, and push. Getting a green
commit from all six people on day 1 is worth more than any single feature.

Find your work: `grep -rn "TODO(member-N)" backend/ frontend/`

---

## Member 1 — Quant / Portfolio
**Owns:** `backend/app/quant/`, `backend/tests/quant/`
**Deliverable:** quant engine + tests

Already done as a reference: `allocation()` and `concentration()` (HHI), with tests.
Follow that shape — pure functions, no I/O, exact numbers, hand-checked tests.

- [ ] `risk_metrics()` — volatility, max drawdown, Sharpe, Sortino, VaR, beta
- [ ] `correlation_matrix()` — pairwise correlation, needs ≥60 overlapping observations
- [ ] Health scorecard: debt burden, diversification, goal progress, market exposure
- [ ] A hand-checked test for every one of them

**Blocked on:** Member 2's `market.get_price_history()`. Until it lands, write your
functions to take a DataFrame argument and test them with a fixture.

---

## Member 2 — Data / Backend
**Owns:** `backend/app/data/`, `backend/app/api/routes/profile.py`
**Deliverable:** FastAPI + PostgreSQL pipeline

You unblock Members 1 and 3. **Ship `get_price_history()` first, even as a cached CSV.**

- [ ] `market.get_price_history()` + on-disk cache under `data/cache/`
- [ ] `market.get_latest_prices()` to mark holdings to market
- [ ] SQLAlchemy models in `data/models.py`, Alembic migration
- [ ] Swap `ProfileRepository`'s dict for real DB sessions (keep the method signatures)
- [ ] Make sure the demo works offline — cache everything before presentation day

---

## Member 3 — ML
**Owns:** `backend/app/ml/`, `notebooks/`
**Deliverable:** model + evaluation notebook

Explore in notebooks, promote only the stable inference path into `app/ml/`.

- [ ] `realized_volatility()` — the baseline everything is compared against
- [ ] `forecast_volatility()` — must return the baseline alongside the forecast
- [ ] `detect_regimes()` — calm vs. stressed labelling
- [ ] Evaluation notebook: does your model actually beat rolling realized vol?

An honest "the baseline won" is a perfectly good result and belongs in the report.

---

## Member 4 — Agent / LLM
**Owns:** `backend/app/agent/`, `backend/app/api/routes/agent.py`, `documents.py`
**Deliverable:** agent orchestration

The keyword router in `orchestrator.select_tools()` works today. Replace it with real
tool calling — but keep it as the fallback when `ANTHROPIC_API_KEY` is missing, so the
demo never hard-fails.

- [ ] LLM tool calling against `tools.to_llm_schema()`
- [ ] `explain()` — system prompt must forbid inventing numbers; copy figures through
- [ ] Register the remaining tools in `TOOL_REGISTRY`
- [ ] `extraction.extract()` — PDF → structured fields, all `needs_confirmation=True`
- [ ] `research.research()` — retrieval with real sources attached

The one rule: **the model picks tools and writes prose. It never computes.**

---

## Member 5 — Simulation
**Owns:** `backend/app/simulation/`, `backend/tests/simulation/`
**Deliverable:** scenario engine

Baseline and market-stress Monte Carlo work end to end. Build out from there.

- [ ] `ALLOCATION_CHANGE` scenario (needs Member 1's correlation matrix)
- [ ] Goal Failure Analysis — attribute shortfall across contributions, market path,
      starting corpus and pauses. This is a genuinely distinctive feature; give it time.
- [ ] Market-stress recovery paths (`recovery_months`)
- [ ] Better return model: fat tails or a block bootstrap over real history
- [ ] Keep every scenario reproducible at `seed=42` — the benchmark depends on it

---

## Member 6 — Frontend / Evaluation
**Owns:** `frontend/`, `backend/app/evaluation/`
**Deliverable:** web app + evaluation report

Two jobs. The benchmark is the one that ends up on everyone's resume — don't leave it
to day 5.

- [ ] Allocation donut, health scorecard, what-if chat panel, scenario comparison table
- [ ] Shaded p10–p90 band on the scenario chart (median-only reads as a prediction)
- [ ] Document upload + the confirmation step before values are used
- [ ] Benchmark: start with `eval_simulation_reproducibility()` — it's cheap and it
      protects everyone else's work
- [ ] 30–50 labelled questions in `evaluation/datasets/tool_selection_cases.json`
- [ ] Write up failure cases and model limitations

---

## Demo script (day 5, ~90 seconds)

One realistic user journey beats a tour of every component.

1. Show the sample profile — portfolio breakdown and risk metrics.
2. Ask: *"What happens if the market falls 30%?"* → scenario result + assumptions.
3. Ask: *"What if I stop my SIP for six months?"* → compare against baseline.
4. Ask: *"What if my income drops for six months?"* → cash runway + goal impact.
5. Open the evidence panel: show that the AI explained **computed** results.

Closing line: *"Our AI understands a financial question, selects the correct
quantitative tool, runs a scenario, and explains the computed result."*

Not: *"our chatbot gives investment advice."*
