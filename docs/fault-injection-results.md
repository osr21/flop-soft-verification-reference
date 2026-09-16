# Seeded SOFT fault-injection results

This is a deterministic **simulation**, not a measurement of a live network,
chain, DA system, challenger population, or adjudicator. It supplies reproducible
attack fixtures and the statistical method needed to replace assumptions with
telemetry. It is published as evidence for
[flop-labs/yellowpaper issue #62](https://github.com/flop-labs/yellowpaper/issues/62).

## Method

Each trial evaluates the ordered challenge path: selection, external data
retrieval, funded challenge submission, timely finalized inclusion, checker
agreement/upheld verdict, and collateral collection. A gate's denominator is
only the trials that passed every earlier gate.

Each conditional factor receives a one-sided Wilson lower confidence bound.
The factor confidence is Bonferroni-adjusted so all six factor bounds hold
simultaneously at 95% confidence for a scenario. The chain bound is their
product. A separate one-sided 95% Wilson bound is calculated directly from
complete-path outcomes. The adversarial model consumes the smaller of those two
bounds:

```text
p_effective_lower = min(simultaneous conditional-chain LCB, direct path LCB)
```

This does not assume gate independence. Correlated failures are sampled once per
trial and applied to all configured affected gates.

Reproduce the tables:

```bash
uv run softverify-faults scenarios/fault-injection.json --format markdown
```

## Results

All scenarios use 50,000 trials, 95% confidence, 40 FLOP aggregate profitable
exposure, and an illustrative 1,000 FLOP collectible miner penalty.

| Attack class | Complete paths | Observed | 95% path LCB | Simultaneous conditional-chain LCB | Economic `p_effective` LCB | Margin (FLOP) |
|---|---:|---:|---:|---:|---:|---:|
| withholding | 5717/50000 | 0.114340 | 0.112020 | 0.107130 | 0.107130 | 67.130 |
| censorship | 4168/50000 | 0.083360 | 0.081349 | 0.077766 | 0.077766 | 37.766 |
| checker_disagreement | 4903/50000 | 0.098060 | 0.095894 | 0.092112 | 0.092112 | 52.112 |
| attempted_unbonding | 4382/50000 | 0.087640 | 0.085582 | 0.082140 | 0.082140 | 42.140 |
| correlated_failure | 8456/50000 | 0.169120 | 0.166380 | 0.161544 | 0.161544 | 121.544 |

### Conditional factor lower bounds by attack class

| Attack class | selected | data | challenge | inclusion | upheld | collectible |
|---|---:|---:|---:|---:|---:|---:|
| withholding | 0.245333 | 0.536092 | 0.912954 | 0.963005 | 0.950545 | 0.974687 |
| censorship | 0.245989 | 0.977773 | 0.937241 | 0.369787 | 0.956334 | 0.975488 |
| checker_disagreement | 0.245969 | 0.978887 | 0.932655 | 0.964786 | 0.436099 | 0.974914 |
| attempted_unbonding | 0.247102 | 0.975741 | 0.933011 | 0.966228 | 0.954652 | 0.395851 |
| correlated_failure | 0.197557 | 0.978401 | 0.934713 | 0.961769 | 0.954090 | 0.974411 |

The economic margins above are synthetic sensitivity results, not evidence that
40 FLOP of real exposure is deterred. In particular, the 1,000 FLOP penalty is
illustrative and is not the published 100 FLOP challenger bond.

## Reading the failures

- Withholding lowers the conditional data-retrieval bound.
- Censorship lowers timely finalized inclusion.
- Checker disagreement lowers the upheld-verdict bound.
- Attempted unbonding lowers actual collateral collection.
- The correlated validator outage is a shared latent event across selection,
  inclusion, and collection. Its attack-level result comes from complete trial
  traces, not multiplication of unconditional marginal rates.

If any eligible gate has no successes, its lower bound and the economic
`p_effective` bound are zero, causing the model to fail closed.

## Live evidence required

Replacing these fixtures requires authenticated, time-windowed telemetry for
eligible selections; DA publication/retrieval/repair; challenge funding and
latency; inclusion/finality timestamps; independent checker outcomes; and
collateral reserved, slashed, and actually collected after competing claims.
Records must retain conditional denominators and common incident identifiers.