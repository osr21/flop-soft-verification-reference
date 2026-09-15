"""Transparent arithmetic helpers for the illustrative SOFT profile.

The Yellow Paper calls ``p_effective`` a conditional chain-rule product.  The
helpers below do not assume that the factors are independent.  Values are
checked and calculated through :class:`decimal.Decimal` before being exposed
as floats, which keeps the examples deterministic while retaining a pleasant
small API.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping


def _probability(value: float | int | str | Decimal, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a finite probability") from exc
    if not result.is_finite() or not Decimal("0") <= result <= Decimal("1"):
        raise ValueError(f"{name} must be between 0 and 1")
    return result


def _amount(value: float | int | str | Decimal, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a finite non-negative amount") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{name} must be a finite non-negative amount")
    return result


def p_effective(
    p_selected: float | int | str | Decimal,
    p_data: float | int | str | Decimal,
    p_challenge: float | int | str | Decimal,
    p_included: float | int | str | Decimal,
    p_upheld: float | int | str | Decimal,
    p_collectible: float | int | str | Decimal,
) -> float:
    """Return the conditional ``p_effective`` product from Yellow Paper §3.5.

    The factors are ordered as selected, data available, challenged, included,
    upheld, and collectible.  They are conditional probabilities, so this
    function intentionally performs multiplication only; it does not infer
    independence or add a sampling correction.
    """

    factors = (
        _probability(p_selected, "p_selected"),
        _probability(p_data, "p_data"),
        _probability(p_challenge, "p_challenge"),
        _probability(p_included, "p_included"),
        _probability(p_upheld, "p_upheld"),
        _probability(p_collectible, "p_collectible"),
    )
    product = Decimal("1")
    for factor in factors:
        product *= factor
    return float(product)


def p_effective_breakdown(
    factors: Mapping[str, float | int | str | Decimal]
    | Iterable[float | int | str | Decimal],
) -> dict[str, object]:
    """Return named factors and their product for audit-friendly vectors.

    A mapping must use the six names in :func:`p_effective`; an iterable must
    contain exactly six values in that same order.
    """

    names = (
        "p_selected",
        "p_data",
        "p_challenge",
        "p_included",
        "p_upheld",
        "p_collectible",
    )
    if isinstance(factors, Mapping):
        missing = [name for name in names if name not in factors]
        extra = [name for name in factors if name not in names]
        if missing or extra:
            raise ValueError(f"factor names must be exactly {names}")
        values = [_probability(factors[name], name) for name in names]
    else:
        values = list(factors)
        if len(values) != len(names):
            raise ValueError("exactly six p_effective factors are required")
        values = [_probability(value, name) for name, value in zip(names, values)]
    product = Decimal("1")
    for value in values:
        product *= value
    return {
        "factors": {name: float(value) for name, value in zip(names, values)},
        "product": float(product),
    }


def max_safe_exposure(
    p_effective_value: float | int | str | Decimal,
    collectible_penalty: float | int | str | Decimal,
) -> float:
    """Return the risk-neutral upper bound ``p_effective × penalty``.

    This is a bound, not a claim of a Nash equilibrium.  A caller seeking
    strict deterrence must keep exposure *below* the returned value.
    """

    probability = _probability(p_effective_value, "p_effective")
    penalty = _amount(collectible_penalty, "collectible_penalty")
    return float(probability * penalty)


def deterrence_margin(
    total_profitable_exposure: float | int | str | Decimal,
    p_effective_value: float | int | str | Decimal,
    collectible_penalty: float | int | str | Decimal,
) -> float:
    """Return expected collectible penalty less profitable exposure.

    A positive result satisfies the illustrative strict inequality from E.45.
    """

    exposure = _amount(total_profitable_exposure, "total_profitable_exposure")
    probability = _probability(p_effective_value, "p_effective")
    penalty = _amount(collectible_penalty, "collectible_penalty")
    return float(probability * penalty - exposure)


def aggregate_exposure(exposures: Iterable[float | int | str | Decimal]) -> float:
    """Sum concurrent channel exposure before applying one collateral cap."""

    total = Decimal("0")
    for index, exposure in enumerate(exposures):
        total += _amount(exposure, f"exposure[{index}]")
    return float(total)


def multi_channel_deterrence_margin(
    exposures: Iterable[float | int | str | Decimal],
    p_effective_value: float | int | str | Decimal,
    collectible_penalty: float | int | str | Decimal,
) -> float:
    """Evaluate E.45 against aggregate, not per-channel, exposure."""

    return deterrence_margin(
        aggregate_exposure(exposures), p_effective_value, collectible_penalty
    )


def challenger_expected_value(
    p_upheld: float | int | str | Decimal,
    reward: float | int | str | Decimal,
    bond: float | int | str | Decimal,
    cost: float | int | str | Decimal = 0,
) -> float:
    """Compute a simple challenger EV with a returned-or-lost bond.

    The challenger posts the bond up front.  On an upheld challenge it receives
    ``reward`` and its bond back (net bond payoff zero); on dismissal the bond
    is lost.  ``cost`` is paid on either branch.  This deliberately leaves
    coalition and timing effects outside the model.
    """

    probability = _probability(p_upheld, "p_upheld")
    reward_amount = _amount(reward, "reward")
    bond_amount = _amount(bond, "bond")
    cost_amount = _amount(cost, "cost")
    ev = probability * reward_amount - (Decimal("1") - probability) * bond_amount - cost_amount
    return float(ev)


def challenger_ev(
    p_upheld: float | int | str | Decimal,
    reward: float | int | str | Decimal,
    bond: float | int | str | Decimal,
    cost: float | int | str | Decimal = 0,
) -> float:
    """Short alias for :func:`challenger_expected_value`."""

    return challenger_expected_value(p_upheld, reward, bond, cost)
