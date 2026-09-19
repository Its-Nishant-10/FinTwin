# FinTwin

**Explainable AI Personal Finance Intelligence & Financial Simulation System**

FinTwin builds a *Personal Financial Digital Twin* — a structured model of a user's
income, expenses, assets, liabilities, portfolio, goals and risk constraints — and lets
them ask what-if questions about possible futures.

> "SIP tells you how you invest regularly; FinTwin analyzes how that investment plan
> interacts with your complete financial situation and possible future scenarios."

**Scope note:** research/decision-support prototype. Not regulated investment advice,
not an autonomous stock picker, and it never presents a simulation as a prediction.

---

## The architectural rule

This is the one thing to get right, and it is what the project is judged on:

| Component | Job |
|---|---|
| **LLM** | Understand the question, select tools, explain the result |
| **Quant code** | Calculate |
| **Simulation engine** | Model scenarios |
| **Retrieval** | Supply evidence |

**The LLM never produces a number that reaches the user.** If you find yourself asking a
model to do arithmetic, you are writing the wrong code.

---

## Prerequisites

- **Python 3.11+** (backend)
- **Node.js 20+** (frontend) — `brew install node` if you don't have it
- **Docker** (optional, only for PostgreSQL)

## Quickstart

```bash
git clone <repo-url> && cd FinTwin
cp .env.example .env          # fill in ANTHROPIC_API_KEY when you need the agent
make setup                    # venv + pip install + npm install
make backend                  # http://localhost:8000/docs
make frontend                 # http://localhost:3000   (separate terminal)
```

Optional, for Member 2's database work:

```bash
make db                       # PostgreSQL on :5432 via Docker
```

Verify your setup:

```bash
make check                    # ruff + pytest — 129 tests should pass
curl localhost:8000/health
```

---

## What already works

- `GET  /profile/sample` — the demo twin (₹3L invested, ₹15k/month, ₹20L in 5 years)
- `POST /portfolio/analyze` — allocation + concentration (HHI)
- **Simulation (Member 5) — complete.** `POST /scenario/run`, `/scenario/whatif`,
  `/scenario/compare`: market crashes (with optional recovery), SIP changes and pauses,
  income shocks, allocation changes, fat-tailed returns, Goal Failure Analysis and the
  SIP needed to close a shortfall
- **Agent (Member 4) — complete.** `POST /agent/ask`: Claude picks tools and explains
  the results. Every figure in its answer is checked against tool output, and a
  deterministic router takes over when no API key is set. `POST /documents/extract` and
  `/documents/confirm`: statement → proposed fields → only user-confirmed values applied
- The dashboard renders baseline vs. a 30% crash from live backend data

Everything else is a typed stub marked `TODO(member-N)` in the module you own.

### Try the agent

```bash
curl -s localhost:8000/profile/sample > /tmp/p.json
curl -s -X POST localhost:8000/agent/ask -H 'Content-Type: application/json' \
  -d "{\"question\": \"What if I stop my SIP for six months?\", \"profile\": $(cat /tmp/p.json)}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['answer']['summary'])"
```

Without `ANTHROPIC_API_KEY` this uses the keyword router and template answers. With a
key, Claude (`claude-opus-5` by default, set `LLM_MODEL` to change it) routes and writes
the answer.

---

## Who owns what

| # | Role | Package | Deliverable |
|---|---|---|---|
| 1 | Quant / Portfolio | `backend/app/quant/` | Risk metrics, allocation, correlation, concentration + tests |
| 2 | Data / Backend | `backend/app/data/` | Market-data pipeline, PostgreSQL, repositories |
| 3 | ML | `backend/app/ml/`, `notebooks/` | Volatility & regime experiments + evaluation notebook |
| 4 | Agent / LLM | `backend/app/agent/` | Tool-calling orchestration, research, document extraction |
| 5 | Simulation | `backend/app/simulation/` | Monte Carlo, stress tests, goal projections |
| 6 | Frontend / Eval | `frontend/`, `backend/app/evaluation/` | Dashboard, benchmark, demo |

You own your package. You touch other packages only through `app/schemas/` — see
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## Five-day plan

| Day | Goal |
|---|---|
| 1 | Everyone set up, owns a package, has one thing working end to end |
| 2 | Build independently: quant engine, data pipeline, first ML experiment, agent tools |
| 3 | Integrate — agents call real tools, scenarios run on real profiles |
| 4 | Explainability, evidence tracking, scenario visualizations, failure handling |
| 5 | Benchmark, UI polish, deploy, README/report, 90-second demo |

## Evaluation — the resume differentiator

Every claim gets measured by `backend/app/evaluation/benchmark.py`: numerical accuracy,
tool-selection accuracy, extraction F1, citation support, simulation reproducibility and
end-to-end latency, plus a written list of failure cases.

**Rule: any number on your resume must come from a run of that harness.**

## Docs

- [Architecture](docs/architecture.md) — layers, data flow, why the LLM doesn't calculate
- [API contracts](docs/api-contracts.md) — endpoints and the shared schemas
- [Team & workflow](docs/team.md) — ownership, day-by-day tasks, demo script
- [Original proposals](docs/proposal/) — the source documents
