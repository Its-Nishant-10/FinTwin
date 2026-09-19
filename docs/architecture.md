# Architecture

## Layers

| Layer | Technology | Job | Owner |
|---|---|---|---|
| Interface | Next.js / React | Data entry, questions, charts | Member 6 |
| AI Orchestrator | LLM + tool calling | Interpret question, choose tools, explain | Member 4 |
| Quant Engine | NumPy / pandas | Portfolio and risk calculations | Member 1 |
| Simulation Engine | NumPy | Monte Carlo + deterministic stress | Member 5 |
| ML Layer | scikit-learn | Volatility / regime experiments | Member 3 |
| Data Layer | PostgreSQL + market APIs | Structured user and market data | Member 2 |
| Evidence Layer | Vector search + source tracking | Retrieval with provenance | Member 4 |
| Backend | FastAPI | Wires it together | Member 2 |

## End-to-end flow

```
INPUT      income, expenses, assets, liabilities, portfolio, goals, risk constraints
             ↓
UNDERSTAND clean → FinancialProfile (the digital twin) → portfolio metrics
             ↓
ASK        user question → orchestrator picks tools
             ↓
CALCULATE  quant engine + ML + simulation engine + retrieval
             ↓
EXPLAIN    assumptions + numerical evidence + plain language + charts
```

## Why the LLM doesn't calculate

A language model is good at interpreting an ambiguous question and at turning a table of
numbers into a sentence a beginner understands. It is unreliable at arithmetic, and it
cannot be unit-tested.

So the split is strict:

- `app/agent/orchestrator.py` decides **which** tool runs.
- `app/quant/` and `app/simulation/` decide **what the number is**.
- The explanation copies numbers through from tool output into
  `Explanation.numbers` — it never restates them from memory.

This is also what makes the benchmark possible: tool selection and numerical accuracy
are separately measurable because they are separate components.

## The Digital Twin

`app/schemas/profile.py::FinancialProfile` is the central object. Everything else
either builds it, measures it, or simulates an alternative version of it.

A scenario is always: **baseline twin + named perturbation + explicit assumptions →
a distribution of outcomes.** Never a single number presented as a forecast.

## Simulation model

Current baseline is geometric Brownian motion with monthly contributions
(`app/simulation/montecarlo.py`). It is deliberately simple and deliberately honest
about being simple:

- Monthly log-returns, drift set so the expected simple return equals the stated
  annual return. A zero-volatility run reproduces plain compounding exactly — that
  property is pinned by a test, because a user checking us against a SIP calculator
  must see the same number.
- Contributions are expressed as a per-month schedule, which is how SIP pauses and
  income shocks are modelled.
- Market shocks are applied multiplicatively at a chosen month on top of the path.

Known limitations to state in the report: normal returns understate tail risk, there is
no modelled correlation between holdings yet, and inflation is not applied to goals.

## Directory map

```
backend/app/
├── schemas/      shared contracts — the seam between all six of us
├── core/         config, logging, errors
├── api/routes/   thin HTTP layer, no business logic
├── quant/        Member 1
├── data/         Member 2
├── ml/           Member 3
├── agent/        Member 4
├── simulation/   Member 5
└── evaluation/   Member 6
frontend/         Member 6
```

Routes stay thin: parse, call the module, return. Logic lives in the module so it can be
tested without HTTP.
