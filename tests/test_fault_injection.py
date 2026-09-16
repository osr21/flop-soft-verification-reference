from __future__ import annotations

from pathlib import Path

import pytest

from softverify.fault_injection import (
    GATES,
    FaultScenario,
    load_scenarios,
    one_sided_wilson_lower_bound,
    simulate_faults,
)


def _scenario(**overrides: object) -> FaultScenario:
    values: dict[str, object] = {
        "name": "test",
        "attack_class": "test",
        "description": "test fixture",
        "trials": 5000,
        "seed": 7,
        "conditional_pass_probabilities": {gate: 0.8 for gate in GATES},
        "total_profitable_exposure": 100.0,
        "collectible_penalty": 1000.0,
    }
    values.update(overrides)
    return FaultScenario(**values)


def test_wilson_lower_bound_handles_empty_and_perfect_samples() -> None:
    assert one_sided_wilson_lower_bound(0, 0) == 0
    assert one_sided_wilson_lower_bound(0, 10) == 0
    assert 0 < one_sided_wilson_lower_bound(10, 10) < 1


def test_zero_conditional_gate_fails_closed() -> None:
    probabilities = {gate: 0.8 for gate in GATES}
    probabilities["challenge_submitted"] = 0.0
    result = simulate_faults(
        _scenario(conditional_pass_probabilities=probabilities)
    )

    assert result.path_successes == 0
    assert result.gate_estimates["timely_finalized_inclusion"].observed_rate is None
    assert result.adversarial_p_effective_lower_bound == 0
    assert result.max_safe_exposure_lower_bound == 0


def test_conditional_product_reconstructs_observed_complete_path() -> None:
    result = simulate_faults(_scenario())
    observed_product = 1.0
    for estimate in result.gate_estimates.values():
        assert estimate.observed_rate is not None
        observed_product *= estimate.observed_rate
    assert observed_product == pytest.approx(
        result.observed_complete_path_probability
    )


def test_correlated_outage_is_measured_at_path_level() -> None:
    baseline = simulate_faults(
        _scenario(conditional_pass_probabilities={gate: 1.0 for gate in GATES})
    )
    outage = simulate_faults(
        _scenario(
            conditional_pass_probabilities={gate: 1.0 for gate in GATES},
            correlated_failure_rate=0.25,
            correlated_failure_gates=GATES,
        )
    )
    assert (
        outage.observed_complete_path_probability
        < baseline.observed_complete_path_probability
    )
    assert outage.adversarial_p_effective_lower_bound <= outage.direct_path_lower_bound


def test_economics_use_lower_bound_not_point_estimate() -> None:
    result = simulate_faults(
        _scenario(conditional_pass_probabilities={gate: 1.0 for gate in GATES})
    )
    assert result.adversarial_p_effective_lower_bound < 1
    assert result.max_safe_exposure_lower_bound < 1000
    assert result.deterrence_margin_lower_bound == pytest.approx(
        result.max_safe_exposure_lower_bound - 100
    )


def test_attack_fixture_covers_required_failure_classes() -> None:
    scenarios = load_scenarios(
        str(Path(__file__).parents[1] / "scenarios" / "fault-injection.json")
    )
    assert {scenario.attack_class for scenario in scenarios} == {
        "withholding",
        "censorship",
        "checker_disagreement",
        "attempted_unbonding",
        "correlated_failure",
    }
    for scenario in scenarios:
        first = simulate_faults(scenario).as_dict()
        second = simulate_faults(scenario).as_dict()
        assert first == second