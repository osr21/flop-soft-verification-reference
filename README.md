# FLOP SOFT verification reference

An independent, non-authoritative proposal for closing the FLOP Network
yellowpaper's open SOFT-tier verification and incentive-model gaps.

This repository combines three reviewable artifacts:

1. a concrete SOFT settlement and dispute profile;
2. an adversarial economic model for effective challenges and collectible
   penalties; and
3. executable state-transition and economic test vectors.

It is based on the published
[FLOP Network Yellow Paper v0.5.0](https://github.com/flop-labs/yellowpaper/blob/main/yellowpaper.md),
especially R3.1–R3.6, §§3.4–3.5 and 12.1, and open items E.33, E.43, E.44,
and E.45.

## Status

**Research proposal; not a FLOP specification, implementation, security audit,
or consensus library.**

The Python package deliberately substitutes strings and booleans for
cryptographic proofs, signatures, VRFs, TOPLOC openings, validator quorums, and
data-availability systems. Passing these tests means an illustrative state
machine follows the proposed outcomes. It does not establish proof-of-useful-
inference soundness.

## Documents

- [Proposed SOFT verification profile](docs/soft-verification-profile.md) —
  actors, commitments, challenge selection, re-execution, state transitions,
  settlement, slashing, privacy, and traceability.
- [Adversarial economic model](docs/adversarial-economic-model.md) —
  conditional `p_effective`, miner-wide exposure, collectible penalties,
  challenger utility, Sybil strategies, and falsifiable parameter tests.
- [Executable vectors](vectors/soft-vectors-v1.json) — cited positive and
  negative transition cases plus one transparent economic scenario.
- [Vector schema](vectors/soft-vectors-v1.schema.json) — machine-readable
  structure for the corpus.
- [Synthetic fault-injection results](docs/fault-injection-results.md) —
  deterministic independent and common-mode challenge-path simulations; not
  real network measurements.

## Reproduce

Python 3.11 or newer is required. Runtime code uses only the standard library.

```bash
python -m pip install pytest
PYTHONPATH=src pytest -q
```

Expected result:

```text
52 passed
```

The tests load every JSON vector, replay its trace through the reference model,
check the expected terminal result and ledger effects, and validate the
economic calculations.

To run the synthetic fault-injection fixtures:

```bash
PYTHONPATH=src uv run python - <<'PY'
from softverify.fault_injection import load_scenarios, simulate_faults

for scenario in load_scenarios("scenarios/fault-injection.json"):
    print(simulate_faults(scenario).as_dict())
PY
```

## What the package tests

- required commitment and model/task binding;
- monotonic co-signed turn receipts;
- duplicate work-credit rejection;
- challenge-window boundaries and standing;
- challenger bond locking and anti-griefing forfeiture;
- temporary and unrecoverable DA failure;
- mismatch and response-timeout fraud outcomes;
- non-delivery refunds;
- conditional effective-challenge probability;
- deterrence margin, safe exposure, and challenger expected value.
- seeded synthetic independent and common-mode fault injection across all six
  challenge-path gates (simulation only, not telemetry).

The vector harness uses shortened block windows so boundary cases stay readable.
The profile document's values are proposals expressed at production scale; the
vector configuration is not a second parameter recommendation.

## Principal finding

The published 2.5% SOFT spot-check value is not an end-to-end fraud-detection
probability, and the published 100 FLOP challenger bond is not a collectible
miner penalty. A deterrence claim needs measured lower bounds for selection,
data availability, challenge action, inclusion, adjudication, and collection,
plus a miner-wide reservation over concurrent profitable exposure.

Until those values are defined and enforced, the simplified inequality

```text
total_profitable_exposure < p_effective × collectible_penalty
```

cannot be evaluated from the two published parameters.

## Relationship to existing upstream reports

This package integrates rather than duplicates several focused reports:

- [#49 — E.45 lacks miner-wide reservation and collectible-penalty formulas](https://github.com/flop-labs/yellowpaper/issues/49)
- [#50 — SOFT demand-floor eligibility lacks a hardware-bound Sybil cost](https://github.com/flop-labs/yellowpaper/issues/50)
- [#55 — no public `flop_meter` implementation or formula](https://github.com/flop-labs/yellowpaper/issues/55)

The proposed profile leaves calibration and `G_n` metering unresolved where the
public specification does. It must not be read as closing those upstream items.

## Suggested review order

1. Check the source/status distinctions in the economic model.
2. Challenge the profile's state transitions and privacy boundaries.
3. Run the vectors and add a counterexample as a failing test.
4. Replace proposed assumptions with measured lower confidence bounds.
5. Promote only decisions that can be traced through the upstream governance
   and specification process.

## Attribution

Prepared as an independent contribution by
`did:key:z6MkrfZePaJ6gTrG746ByXGgtzz8Z8SCQbehTMt6TQGcc5dQ`.

The FLOP Network yellowpaper is cited as the source specification. This
repository does not imply endorsement by FLOP Labs.

## License

MIT. See [LICENSE](LICENSE).