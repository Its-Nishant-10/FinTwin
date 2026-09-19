source: FinTwin knowledge note on the simulation method used by the scenario engine

## What a Monte Carlo simulation is

A Monte Carlo simulation runs thousands of possible future market paths under stated assumptions about average return and volatility, then reports the spread of outcomes. It answers "what range of results is plausible under these assumptions", not "what will happen".

## Reading percentiles

The median (50th percentile) is the middle outcome: half the simulated paths end above it and half below. The 10th percentile is a poor but not extreme outcome, and the 90th a good one. The success probability of a goal is the share of simulated paths that reach the target.

## Limitations of simulation

Results are only as good as the assumptions. Normal-distribution models understate how often markets fall sharply in a single month, historical averages may not repeat, and the model ignores taxes, fees and changes in the investor's behaviour unless they are modelled explicitly. FinTwin shows the assumptions beside every result for this reason.
