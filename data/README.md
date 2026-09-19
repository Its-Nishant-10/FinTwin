# Data

- `sample/` — small, committed fixtures used by tests and the demo.
- `raw/`, `cache/` — gitignored. Market-data downloads land here.
- `benchmark_results.json` — written by `python -m app.evaluation.benchmark`.

**Never commit real user financial data.** Sample data must be synthetic.

Member 2: cache everything the demo needs before presentation day. The demo must run
without network access.
