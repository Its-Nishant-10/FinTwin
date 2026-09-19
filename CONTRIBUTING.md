# Contributing to FinTwin

Six people, five days, one repo. These rules exist so we spend the time building
instead of resolving merge conflicts.

## The ownership rule

Each person owns one package. **Edit files in your own package freely. Never edit
someone else's package without telling them.**

| Owner | Package |
|---|---|
| Member 1 | `backend/app/quant/`, `backend/tests/quant/` |
| Member 2 | `backend/app/data/`, `backend/app/api/routes/profile.py` |
| Member 3 | `backend/app/ml/`, `notebooks/` |
| Member 4 | `backend/app/agent/`, `backend/app/api/routes/agent.py`, `documents.py` |
| Member 5 | `backend/app/simulation/`, `backend/tests/simulation/` |
| Member 6 | `frontend/`, `backend/app/evaluation/` |

Shared, needs an announcement before you change it:
`backend/app/schemas/` · `backend/app/core/` · `backend/app/main.py` · `.env.example` ·
`docker-compose.yml`

## Changing a schema

`backend/app/schemas/` is the contract between all six of us. Changing it breaks other
people's code silently.

1. Post in the team channel: what you're changing and why.
2. Open a PR touching **only** the schema + the mirror in `frontend/lib/types.ts`.
3. Tag everyone whose module consumes it.
4. Merge fast — a schema PR sitting open blocks people.

Adding an optional field is safe. Renaming or removing one is not.

## Branches and commits

```bash
git checkout -b quant/concentration-metrics    # <area>/<short-description>
```

Areas: `quant` · `data` · `ml` · `agent` · `sim` · `frontend` · `eval` · `docs` · `infra`

Conventional commits, present tense:

```
feat(quant): add HHI concentration metric
fix(sim): correct drift so zero-vol runs match deterministic compounding
test(agent): cover tool selection for income-shock questions
docs(readme): document the benchmark rule
```

Commit early and often. A small commit that passes tests beats a perfect one you
haven't pushed.

## Before every push

```bash
make check     # ruff + pytest — must be green
```

CI runs the same thing. Don't push red.

## Pull requests

Open a PR, get one review, merge. Keep them small — a PR over ~400 lines will not get a
real review on a five-day timeline.

## Code standards

- **Type hints on every function.** Pydantic models for anything crossing a boundary.
- **Docstrings say *why*.** The code already says what.
- **No LLM arithmetic.** If a number reaches the user, deterministic code produced it.
- **No magic numbers.** Assumptions go in `Assumptions`, config goes in `app/core/config.py`.
- **Missing beats wrong.** Raise `InsufficientDataError` rather than returning `0.0` for a
  metric you can't honestly compute.
- **Every public quant/sim function needs a test with a hand-checked number.**
- **Never commit real financial data, `.env`, or API keys.**

## Working with the stubs

Functions you own are marked:

```python
def risk_metrics(...) -> RiskMetrics:
    """TODO(member-1): ..."""
```

Grep your own list any time:

```bash
grep -rn "TODO(member-1)" backend/
```

Implement it, delete the TODO, add a test. Keep the signature — other people are
already calling it.
