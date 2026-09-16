"""Seeded SOFT challenge-path fault injection with conservative confidence bounds.

This is a synthetic experiment harness, not production telemetry.  Trials record
the complete ordered path so conditional rates and correlated failures are
measured directly rather than reconstructed from unconditional marginals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json
import math
import random
from statistics import NormalDist
from typing import Mapping

from .economics import deterrence_margin, max_safe_exposure


GATES = (
    "selected",
    "da_available",
    "challenge_submitted",
    "timely_finalized_inclusion",
    "upheld_verdict",
    "collateral_collection",
)


@dataclass(frozen=True)
class FaultScenario:
    """A reproducible attack scenario using ordered conditional gate rates."""

    name: str
    attack_class: str
    description: str
    trials: int
    seed: int
    conditional_pass_probabilities: Mapping[str, float]
    correlated_failure_rate: float = 0.0
    correlated_failure_gates: tuple[str, ...] = ()
    total_profitable_exposure: float = 0.0
    collectible_penalty: float = 0.0
    confidence: float = 0.95

    def __post_init__(self) -> None:
        if self.trials < 1:
            raise ValueError("trials must be positive")
        if set(self.conditional_pass_probabilities) != set(GATES):
            raise ValueError(
                f"conditional_pass_probabilities must contain exactly {GATES}"
            )
        for gate, probability in self.conditional_pass_probabilities.items():
            if not 0 <= float(probability) <= 1:
                raise ValueError(f"{gate} probability must be between 0 and 1")
        if not 0 <= self.correlated_failure_rate <= 1:
            raise ValueError("correlated_failure_rate must be between 0 and 1")
        unknown = set(self.correlated_failure_gates) - set(GATES)
        if unknown:
            raise ValueError(f"unknown correlated failure gates: {sorted(unknown)}")
        if not 0 < self.confidence < 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.total_profitable_exposure < 0 or self.collectible_penalty < 0:
            raise ValueError("economic amounts must be non-negative")


@dataclass(frozen=True)
class GateEstimate:
    successes: int
    eligible_trials: int
    observed_rate: float | None
    lower_confidence_bound: float


@dataclass(frozen=True)
class FaultSimulationResult:
    scenario: str
    attack_class: str
    description: str
    trials: int
    seed: int
    confidence: float
    correlated_failure_rate: float
    correlated_failure_gates: tuple[str, ...]
    gate_estimates: dict[str, GateEstimate]
    path_successes: int
    observed_complete_path_probability: float
    conditional_chain_lower_bound: float
    direct_path_lower_bound: float
    adversarial_p_effective_lower_bound: float
    max_safe_exposure_lower_bound: float
    deterrence_margin_lower_bound: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def one_sided_wilson_lower_bound(
    successes: int, trials: int, confidence: float = 0.95
) -> float:
    """Return a one-sided Wilson score lower confidence bound."""

    if trials < 0 or not 0 <= successes <= trials:
        raise ValueError("successes must be between zero and trials")
    if trials == 0 or successes == 0:
        return 0.0
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    observed = successes / trials
    z = NormalDist().inv_cdf(confidence)
    z2 = z * z
    denominator = 1 + z2 / trials
    centre = observed + z2 / (2 * trials)
    radius = z * math.sqrt(
        observed * (1 - observed) / trials + z2 / (4 * trials * trials)
    )
    return max(0.0, (centre - radius) / denominator)


def simulate_faults(scenario: FaultScenario) -> FaultSimulationResult:
    """Run one deterministic ordered-path experiment."""

    rng = random.Random(scenario.seed)
    successes = {gate: 0 for gate in GATES}
    eligible = {gate: 0 for gate in GATES}
    path_successes = 0
    correlated_gates = set(scenario.correlated_failure_gates)

    for _ in range(scenario.trials):
        common_failure = rng.random() < scenario.correlated_failure_rate
        path_passed = True
        for gate in GATES:
            if not path_passed:
                continue
            eligible[gate] += 1
            passed = not (common_failure and gate in correlated_gates)
            if passed:
                passed = rng.random() < float(
                    scenario.conditional_pass_probabilities[gate]
                )
            if passed:
                successes[gate] += 1
            else:
                path_passed = False
        if path_passed:
            path_successes += 1

    # Bonferroni adjustment makes the six factor bounds simultaneous at the
    # scenario confidence level; no independence between factors is assumed.
    factor_confidence = 1 - (1 - scenario.confidence) / len(GATES)
    estimates: dict[str, GateEstimate] = {}
    chain_lower = 1.0
    for gate in GATES:
        denominator = eligible[gate]
        rate = successes[gate] / denominator if denominator else None
        lower = one_sided_wilson_lower_bound(
            successes[gate], denominator, factor_confidence
        )
        estimates[gate] = GateEstimate(successes[gate], denominator, rate, lower)
        chain_lower *= lower

    direct_lower = one_sided_wilson_lower_bound(
        path_successes, scenario.trials, scenario.confidence
    )
    effective_lower = min(chain_lower, direct_lower)
    safe_exposure = max_safe_exposure(
        effective_lower, scenario.collectible_penalty
    )
    return FaultSimulationResult(
        scenario=scenario.name,
        attack_class=scenario.attack_class,
        description=scenario.description,
        trials=scenario.trials,
        seed=scenario.seed,
        confidence=scenario.confidence,
        correlated_failure_rate=scenario.correlated_failure_rate,
        correlated_failure_gates=scenario.correlated_failure_gates,
        gate_estimates=estimates,
        path_successes=path_successes,
        observed_complete_path_probability=path_successes / scenario.trials,
        conditional_chain_lower_bound=chain_lower,
        direct_path_lower_bound=direct_lower,
        adversarial_p_effective_lower_bound=effective_lower,
        max_safe_exposure_lower_bound=safe_exposure,
        deterrence_margin_lower_bound=deterrence_margin(
            scenario.total_profitable_exposure,
            effective_lower,
            scenario.collectible_penalty,
        ),
    )


def load_scenarios(path: str) -> list[FaultScenario]:
    """Load JSON scenarios using only the standard library."""

    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return [
        FaultScenario(
            **{
                **item,
                "correlated_failure_gates": tuple(
                    item.get("correlated_failure_gates", ())
                ),
            }
        )
        for item in payload
    ]


def render_markdown(results: list[FaultSimulationResult]) -> str:
    """Render stable public evidence tables from simulation results."""

    lines = [
        "| Attack class | Complete paths | Observed | 95% path LCB "
        "| Simultaneous conditional-chain LCB | Economic `p_effective` LCB "
        "| Margin (FLOP) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        lines.append(
            f"| {result.attack_class} | {result.path_successes}/{result.trials} "
            f"| {result.observed_complete_path_probability:.6f} "
            f"| {result.direct_path_lower_bound:.6f} "
            f"| {result.conditional_chain_lower_bound:.6f} "
            f"| {result.adversarial_p_effective_lower_bound:.6f} "
            f"| {result.deterrence_margin_lower_bound:.3f} |"
        )
    lines.extend(
        [
            "",
            "| Attack class | selected | data | challenge | inclusion "
            "| upheld | collectible |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for result in results:
        bounds = [
            result.gate_estimates[gate].lower_confidence_bound for gate in GATES
        ]
        lines.append(
            f"| {result.attack_class} | "
            + " | ".join(f"{bound:.6f}" for bound in bounds)
            + " |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "scenarios", nargs="?", default="scenarios/fault-injection.json"
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    results = [simulate_faults(scenario) for scenario in load_scenarios(args.scenarios)]
    if args.format == "markdown":
        print(render_markdown(results))
    else:
        print(json.dumps([result.as_dict() for result in results], indent=2))


if __name__ == "__main__":
    main()