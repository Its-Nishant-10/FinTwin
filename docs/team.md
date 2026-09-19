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

**Status: complete.** See the "Agent pipeline" section of [architecture.md](architecture.md).

- [x] LLM tool calling (`orchestrator.py`, `llm.py`), with refusal fallback and
      deterministic fallback on any API failure
- [x] Grounding check: the LLM's prose is discarded if it cites a figure no tool
      produced (`grounding.py`)
- [x] All 8 tools registered with JSON schemas (`tools.py`); `forecast_volatility`
      reports "not built yet" until Member 3 ships it
- [x] Keyword router that also extracts arguments (`router.py`), the benchmark baseline
- [x] Document extraction: CSV by column, text/PDF via LLM structured output with
      every figure checked against the source, regex fallback; `/documents/confirm`
      applies only user-confirmed fields (`extraction.py`)
- [x] Research: TF-IDF retrieval over `agent/knowledge/*.md`, every passage sourced
      (`research.py`)

Still open:
- [ ] The knowledge base is small and hand-written; historical figures in
      `drawdowns.md` are approximate and should be checked against NSE data
- [ ] Retrieval is lexical; swap `_Index` for embeddings if time allows
- [ ] Scanned PDFs need OCR (not supported)
- [ ] Measure the real-LLM path: tool-selection accuracy vs. `router.select_tools`,
      grounding-check hit rate, latency (with Member 6)

The one rule: **the model picks tools and writes prose. It never computes.**

---

## Member 5 — Simulation
**Owns:** `backend/app/simulation/`, `backend/tests/simulation/`
**Deliverable:** scenario engine

**Status: complete.** See "Simulation model" in [architecture.md](architecture.md).

- [x] `ALLOCATION_CHANGE`: both sides use asset-class assumptions
      (`simulation/assumptions.py`), not Member 1's correlation matrix, so it isn't blocked
- [x] Goal Failure Analysis: exact Shapley attribution of the shortfall across the
      baseline plan and each perturbation, plus the SIP needed to close it
- [x] Market-stress recovery paths (`recovery_months`)
- [x] Fat-tailed returns (`return_model="student_t"`)
- [x] Income shocks limited by actual cash flow; goals scored at their own horizon
- [x] `/scenario/whatif` (auto baseline) and 422s instead of 500s for bad input
- [x] Every scenario reproducible at `seed=42`, pinned by tests

Still open:
- [ ] Block bootstrap from real price history (needs Member 2's `get_price_history`)
- [ ] Replace the illustrative asset-class assumptions with estimates from real data
- [ ] Regime-conditioned volatility (with Member 3)

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
