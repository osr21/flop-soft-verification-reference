"""Deterministic synthetic fault-injection experiments for SOFT challenge paths.

This module is a simulator, not a network measurement harness.  Its outputs
are useful for checking arithmetic, fixture stability, and correlated-failure
intuition only.  Every gate is sampled from a seeded PRNG and therefore says
nothing about production availability or adversarial behavior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import random
from typing import Mapping

from .economics import deterrence_margin, max_safe_exposure, p_effective


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
    """A reproducible synthetic scenario.

    ``common_mode_failure_rate`` is the probability of a latent event that
    makes every gate fail in the same trial.  In common-mode scenarios the
    remaining independent probabilities are adjusted so each named gate keeps
    the configured marginal probability.  This makes independent and
    common-mode comparisons meaningful rather than changing both the marginals
    and the dependence structure.
    """

    name: str
    trials: int
    seed: int
    unconditional_marginal_pass_probabilities: Mapping[str, float]
    failure_mode: str = "independent"
    common_mode_failure_rate: float = 0.0
    total_profitable_exposure: float = 0.0
    collectible_penalty: float = 0.0

    def __post_init__(self) -> None:
        if self.trials < 1:
            raise ValueError("trials must be positive")
        if self.failure_mode not in {"independent", "common_mode"}:
            raise ValueError("failure_mode must be independent or common_mode")
        if set(self.unconditional_marginal_pass_probabilities) != set(GATES):
            raise ValueError(
                "unconditional_marginal_pass_probabilities must contain "
                f"exactly {GATES}"
            )
        for gate in GATES:
            probability = float(self.unconditional_marginal_pass_probabilities[gate])
            if not 0 <= probability <= 1:
                raise ValueError(f"{gate} probability must be between 0 and 1")
        if not 0 <= self.common_mode_failure_rate <= 1:
            raise ValueError("common_mode_failure_rate must be between 0 and 1")
        if self.common_mode_failure_rate > 1 - max(
            float(self.unconditional_marginal_pass_probabilities[gate])
            for gate in GATES
        ):
            raise ValueError(
                "common-mode failure rate leaves no valid marginal-preserving pass rate"
            )
        if self.total_profitable_exposure < 0 or self.collectible_penalty < 0:
            raise ValueError("economic amounts must be non-negative")


@dataclass(frozen=True)
class FaultSimulationResult:
    """Aggregate result from one deterministic synthetic run."""

    scenario: str
    trials: int
    seed: int
    failure_mode: str
    common_mode_failure_rate: float
    gate_pass_counts: dict[str, int]
    path_successes: int
    observed_gate_rates: dict[str, float]
    observed_complete_path_probability: float
    independence_product: float
    sequential_conditional_rates: dict[str, float | None]
    sequential_conditional_product: float
    max_safe_exposure: float
    deterrence_margin: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _adjusted_independent_probability(
    marginal: float, common_mode_failure_rate: float
) -> float:
    if common_mode_failure_rate == 1:
        return 0.0
    return marginal / (1 - common_mode_failure_rate)


def simulate_faults(scenario: FaultScenario) -> FaultSimulationResult:
    """Run a deterministic synthetic gate-path experiment."""

    rng = random.Random(scenario.seed)
    counts = {gate: 0 for gate in GATES}
    prefix_counts = {gate: 0 for gate in GATES}
    successes = 0
    common_rate = scenario.common_mode_failure_rate
    adjusted = {
        gate: _adjusted_independent_probability(
            float(scenario.unconditional_marginal_pass_probabilities[gate]),
            common_rate,
        )
        for gate in GATES
    }

    for _ in range(scenario.trials):
        common_failure = (
            scenario.failure_mode == "common_mode" and rng.random() < common_rate
        )
        path_passed = True
        for gate in GATES:
            passed = not common_failure and rng.random() < (
                adjusted[gate] if scenario.failure_mode == "common_mode" else float(
                    scenario.unconditional_marginal_pass_probabilities[gate]
                )
            )
            if passed:
                counts[gate] += 1
            if path_passed and passed:
                prefix_counts[gate] += 1
            path_passed = path_passed and passed
        if path_passed:
            successes += 1

    independence_product = p_effective(
        *(
            float(scenario.unconditional_marginal_pass_probabilities[gate])
            for gate in GATES
        )
    )
    observed = successes / scenario.trials
    sequential_rates: dict[str, float | None] = {}
    denominator = scenario.trials
    for gate in GATES:
        if denominator == 0:
            sequential_rates[gate] = None
        else:
            sequential_rates[gate] = prefix_counts[gate] / denominator
        denominator = prefix_counts[gate]
    sequential_product = 1.0
    for rate in sequential_rates.values():
        if rate is None:
            sequential_product = 0.0
            break
        sequential_product *= rate
    safe_exposure = max_safe_exposure(observed, scenario.collectible_penalty)
    return FaultSimulationResult(
        scenario=scenario.name,
        trials=scenario.trials,
        seed=scenario.seed,
        failure_mode=scenario.failure_mode,
        common_mode_failure_rate=common_rate,
        gate_pass_counts=counts,
        path_successes=successes,
        observed_gate_rates={
            gate: counts[gate] / scenario.trials for gate in GATES
        },
        observed_complete_path_probability=observed,
        independence_product=independence_product,
        sequential_conditional_rates=sequential_rates,
        sequential_conditional_product=sequential_product,
        max_safe_exposure=safe_exposure,
        deterrence_margin=deterrence_margin(
            scenario.total_profitable_exposure, observed, scenario.collectible_penalty
        ),
    )


def load_scenarios(path: str) -> list[FaultScenario]:
    """Load a JSON scenario fixture using only the standard library."""

    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return [FaultScenario(**item) for item in payload]
