from __future__ import annotations

from pathlib import Path

import pytest

from softverify.fault_injection import (
    GATES,
    FaultScenario,
    load_scenarios,
    simulate_faults,
)


def _scenario(**overrides: object) -> FaultScenario:
    values: dict[str, object] = {
        "name": "test",
        "trials": 2000,
        "seed": 7,
        "unconditional_marginal_pass_probabilities": {gate: 0.8 for gate in GATES},
        "total_profitable_exposure": 500.0,
        "collectible_penalty": 1000.0,
    }
    values.update(overrides)
    return FaultScenario(**values)


def test_zero_gate_failure_makes_path_probability_zero() -> None:
    probabilities = {gate: 0.8 for gate in GATES}
    probabilities["challenge_submitted"] = 0.0
    result = simulate_faults(
        _scenario(unconditional_marginal_pass_probabilities=probabilities)
    )

    assert result.path_successes == 0
    assert result.observed_complete_path_probability == 0.0
    assert result.sequential_conditional_rates["timely_finalized_inclusion"] is None
    assert result.max_safe_exposure == 0.0


def test_common_mode_failures_change_selection_path_despite_same_marginals() -> None:
    independent = simulate_faults(_scenario(name="independent"))
    correlated = simulate_faults(
        _scenario(
            name="correlated",
            failure_mode="common_mode",
            common_mode_failure_rate=0.1,
        )
    )

    assert correlated.observed_gate_rates["selected"] == pytest.approx(
        independent.observed_gate_rates["selected"], abs=0.04
    )
    assert (
        correlated.observed_complete_path_probability
        > independent.observed_complete_path_probability
    )


@pytest.mark.parametrize("failure_mode,common_mode_failure_rate", [
    ("independent", 0.0),
    ("common_mode", 0.1),
])
def test_sequential_conditional_product_equals_observed_path(
    failure_mode: str, common_mode_failure_rate: float
) -> None:
    result = simulate_faults(
        _scenario(
            failure_mode=failure_mode,
            common_mode_failure_rate=common_mode_failure_rate,
        )
    )

    assert result.sequential_conditional_product == pytest.approx(
        result.observed_complete_path_probability
    )


def test_backed_collateral_boundary_uses_observed_effective_probability() -> None:
    scenario = _scenario(
        trials=1000,
        seed=2,
        unconditional_marginal_pass_probabilities={gate: 1.0 for gate in GATES},
        total_profitable_exposure=1000.0,
        collectible_penalty=1000.0,
    )
    result = simulate_faults(scenario)

    assert result.observed_complete_path_probability == 1.0
    assert result.max_safe_exposure == 1000.0
    assert result.deterrence_margin == 0.0

    backed = simulate_faults(
        _scenario(
            unconditional_marginal_pass_probabilities={gate: 1.0 for gate in GATES},
            total_profitable_exposure=999.0,
            collectible_penalty=1000.0,
        )
    )
    assert backed.deterrence_margin > 0


def test_scenario_fixture_loads() -> None:
    scenarios = load_scenarios(
        str(Path(__file__).parents[1] / "scenarios" / "fault-injection.json")
    )
    assert [scenario.name for scenario in scenarios] == [
        "independent-baseline",
        "common-mode-outage",
    ]