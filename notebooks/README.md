# Notebooks

Exploration space, mainly for Member 3 (ML).

Conventions:

- Name them `NN-owner-topic.ipynb`, e.g. `01-member3-volatility-baseline.ipynb`.
- **Clear all outputs before committing** — notebook diffs are unreadable otherwise.
- Notebooks are for exploring. Once something works, promote it into `backend/app/ml/`
  where it can be imported and tested. Nothing in the API should import a notebook.

```python
import sys; sys.path.append("../backend")
from app.data.sample import load_sample_profile
from app.quant import analytics

profile = load_sample_profile()
analytics.analyze(profile)
```
