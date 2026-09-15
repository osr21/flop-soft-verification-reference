from __future__ import annotations

import pytest

from softverify.economics import (
    aggregate_exposure,
    challenger_expected_value,
    deterrence_margin,
    max_safe_exposure,
    multi_channel_deterrence_margin,
    p_effective,
    p_effective_breakdown,
)


def test_p_effective_is_conditional_chain_product() -> None:
    factors = (0.5, 0.9, 0.8, 0.95, 0.75, 0.8)
    assert p_effective(*factors) == pytest.approx(0.2052)
    breakdown = p_effective_breakdown(factors)
    assert breakdown["product"] == pytest.approx(0.2052)
    assert breakdown["factors"]["p_selected"] == 0.5


def test_deterrence_bound_and_margin() -> None:
    assert max_safe_exposure(0.2, 1000) == pytest.approx(200)
    assert deterrence_margin(150, 0.2, 1000) == pytest.approx(50)
    assert deterrence_margin(250, 0.2, 1000) < 0


def test_multi_channel_exposure_uses_one_aggregate_cap() -> None:
    assert aggregate_exposure([60, 70, 80]) == pytest.approx(210)
    assert multi_channel_deterrence_margin([60, 70, 80], 0.5, 500) == pytest.approx(40)


def test_challenger_ev_return_or_loss_of_bond() -> None:
    # A returned bond is principal, not a reward: .75 * 100 - .25 * 100.
    assert challenger_expected_value(0.75, 100, 100) == pytest.approx(50)
    assert challenger_expected_value(0.5, 0, 100, 10) == pytest.approx(-60)


@pytest.mark.parametrize(
    "args",
    [
        (-0.1, 1, 1, 1, 1, 1),
        (2, 1, 1, 1, 1, 1),
    ],
)
def test_probability_inputs_are_checked(args: tuple[float, ...]) -> None:
    with pytest.raises(ValueError):
        p_effective(*args)
