# Synthetic SOFT fault-injection results

This document records a deterministic **simulation**, not a measurement of a
network, chain, DA system, challenger population, or adjudicator.  The
experiment uses a seeded standard-library PRNG and six gates evaluated in order:

1. selected;
2. data available;
3. a funded, timely challenge is submitted;
4. challenge inclusion is timely and finalized;
5. the verdict is upheld; and
6. miner collateral is collectible.

Run it with:

```bash
PYTHONPATH=src uv run python - <<'PY'
from softverify.fault_injection import load_scenarios, simulate_faults

for scenario in load_scenarios("scenarios/fault-injection.json"):
    result = simulate_faults(scenario)
    print(result.as_dict())
PY
```

## Fixture results

Both scenarios use 20,000 trials and the same unconditional synthetic marginal
pass probabilities. The independent baseline produces 4,102 complete paths
(`observed_complete_path_probability = 0.2051`), while the common-mode fixture
produces 5,094 (`observed_complete_path_probability = 0.2547`). The
`independence_product` of the six unconditional marginals is `0.2052` in both
scenarios; it is a comparison value, not an observed result.

Each result also reports sequential conditional gate rates. For each gate, the
denominator is the count passing every previous gate; when that denominator is
zero, the rate is explicitly `null`. Multiplying the sequential conditional
rates (treating a `null` after a zero denominator as zero) equals the observed
complete-path frequency exactly. Common-mode comparisons preserve the
unconditional marginals, not the sequential conditional factors: the latter
change because the dependence structure changes. None of these outputs are
network measurements.

`max_safe_exposure` and `deterrence_margin` are calculated through the existing
economic helpers using the observed synthetic complete-path frequency.

## What real telemetry would be needed

Replacing these fixtures with an empirical lower bound requires authenticated,
time-windowed telemetry for:

- the eligible population and selection events;
- DA publication, retrieval, repair, and permanent unavailability;
- challenge funding and action latency after selection and DA availability;
- inclusion and finality timestamps for challenge transactions;
- independent adjudication outcomes and upheld-verdict evidence; and
- collateral reserved, slashed, and actually collectible after competing claims.

The data must preserve the conditional denominators and identify common-mode
events (for example, a validator outage affecting selection, inclusion, and
collection together).  Aggregated success counts without those denominators
cannot establish the published SOFT deterrence claim.  This package supplies
only reproducible failure-injection mechanics and economic sensitivity checks.