from __future__ import annotations

import json
from pathlib import Path

import pytest

from softverify import (
    SoftState,
    append_turn,
    collateral_conserved,
    challenger_ev,
    deterrence_margin,
    escrow_conserved,
    fund_miner_collateral,
    make_turn_commitment,
    max_safe_exposure,
    multi_channel_deterrence_margin,
    open_session,
    p_effective,
    run_trace,
)


ROOT = Path(__file__).parents[1]
VECTORS = json.loads((ROOT / "vectors/soft-vectors-v1.json").read_text())


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=lambda vector: vector["id"])
def test_state_vector(vector: dict) -> None:
    _, results = run_trace(vector["trace"])
    result = results[-1]
    expected = vector["expected"]
    assert result.accepted is expected["accepted"]
    assert result.code == expected["code"]
    if result.session is not None:
        assert result.session.status.value == expected["status"]
    elif expected["status"] != "absent":
        raise AssertionError("vector expected a session")
    for key in ("credited_gn", "refund", "miner_slash", "bond_forfeited"):
        if key in expected:
            assert result.effects[key] == expected[key]
    if "b_col_lower" in expected:
        assert result.effects["b_col_lower"] == pytest.approx(expected["b_col_lower"])
        assert result.state.miner_collateral_reserved[result.session.miner] == expected["b_col_lower"]
        assert result.state.miner_collateral_deposited[result.session.miner] == expected["b_col_lower"]
    if "miner_slash" in expected and expected["miner_slash"] > 0:
        assert result.effects["collectible_slash"] == expected["miner_slash"]
    if result.session is not None:
        assert escrow_conserved(result.state, result.session.session_id)
        assert collateral_conserved(result.state, result.session.miner)
        if "safety_margin" in expected:
            assert result.session.safety_margin == pytest.approx(expected["safety_margin"])


def test_vectors_have_citations_and_requirement_ids() -> None:
    requirement_ids = {item["id"] for item in VECTORS["requirements"]}
    assert len(VECTORS["vectors"]) >= 10
    for vector in VECTORS["vectors"]:
        assert vector["source_citations"]
        assert set(vector["requirement_ids"]) <= requirement_ids


def test_economic_vector() -> None:
    item = VECTORS["economics"]
    factors = item["factors"]
    effective = p_effective(**factors)
    safe = max_safe_exposure(effective, item["expected"]["collectible_penalty"])
    margin = deterrence_margin(item["expected"]["total_profitable_exposure"], effective, item["expected"]["collectible_penalty"])
    ev = challenger_ev(0.75, 100, 100, 0)
    assert effective == pytest.approx(item["expected"]["p_effective"])
    assert safe == pytest.approx(item["expected"]["max_safe_exposure"])
    assert margin == pytest.approx(item["expected"]["deterrence_margin"])
    assert ev == pytest.approx(item["expected"]["challenger_ev"])


def _valid_turn(state: SoftState, session_id: str) -> dict:
    session = state.sessions[session_id]
    fields = {
        "session_id": session_id,
        "index": 0,
        "task_hash": session.task_hash,
        "model_hash": session.model_hash,
        "payload_hash": session.payload_hash,
        "decode_policy_hash": session.decode_policy_hash,
        "precision": session.precision,
        "backend": session.backend,
        "gpu_cell": session.gpu_cell,
        "prompt_hash": session.prompt_hash,
        "input_hash": session.input_hash,
        "output_hash": "out",
        "gn": 7,
        "toploc_root": session.toploc_root,
        "activation_commitment": session.activation_commitment,
        "da_reference": session.da_reference,
        "nonce": session.nonce,
    }
    fields["commitment"] = make_turn_commitment(profile=session.profile, **fields)
    return fields


@pytest.mark.parametrize(
    "field",
    [
        "session_id",
        "profile",
        "index",
        "task_hash",
        "model_hash",
        "payload_hash",
        "decode_policy_hash",
        "precision",
        "backend",
        "gpu_cell",
        "prompt_hash",
        "input_hash",
        "output_hash",
        "gn",
        "toploc_root",
        "activation_commitment",
        "da_reference",
        "nonce",
    ],
)
def test_every_turn_bound_field_rejects_mutation(field: str) -> None:
    state = SoftState()
    assert fund_miner_collateral(state, miner="miner-a", amount=50).accepted
    opened = open_session(
        state,
        session_id="mutation",
        agent="agent-a",
        miner="miner-a",
        task_hash="task",
        model_hash="model",
        payload_hash="payload",
        decode_policy_hash="decode",
        precision="fp16",
        backend="backend",
        gpu_cell="gpu",
        prompt_hash="prompt",
        input_hash="input",
        profile="profile",
        toploc_root="root",
        commitment="activation",
        da_reference="da",
        nonce=11,
        escrow=20,
        reserved_collateral=50,
        declared_exposure=20,
        p_effective_lower_bound=0.5,
    )
    assert opened.accepted
    event = _valid_turn(state, "mutation")
    if field == "session_id":
        event[field] = "other-session"
    elif field == "profile":
        state.sessions["mutation"].profile += "-mutated"
    elif field == "index":
        event[field] = 1
    elif field in {"gn", "nonce"}:
        event[field] += 1
    elif field == "activation_commitment":
        event[field] = "activation-mutated"
    elif field == "da_reference":
        event[field] = "da-mutated"
    else:
        event[field] = f"{event[field]}-mutated"
    result = append_turn(state, **event)
    assert not result.accepted, field
    assert not state.sessions["mutation"].turns


def test_matching_response_is_provisional_then_finalizes() -> None:
    vector = next(item for item in VECTORS["vectors"] if item["id"] == "honest-dismissal")
    state, results = run_trace(vector["trace"])
    dismissal = results[-2]
    assert dismissal.code == "DISMISSED"
    assert dismissal.session is not None
    assert dismissal.effects["status_after"] == "settled"
    assert state.challenger_bond_forfeited["agent-a"] == 100
    assert state.challenger_available["agent-a"] == 0
    assert results[-1].code == "FINALIZED"
    assert state.sessions["s-dismiss"].status.value == "finalized"


def test_matching_response_allows_one_fresh_challenge() -> None:
    trace = next(item for item in VECTORS["vectors"] if item["id"] == "honest-dismissal")["trace"][:-1]
    trace.extend(
        [
            {"op": "fund_challenger", "challenger": "agent-a", "amount": 100},
            {"op": "challenge", "session_id": "s-dismiss", "challenger": "agent-a", "block": 5, "bond": 100},
        ]
    )
    state, results = run_trace(trace)
    assert results[-1].code == "CHALLENGE_OPENED"
    assert state.sessions["s-dismiss"].challenge_count == 2


def test_da_unavailable_before_lock_does_not_return_unposted_bond() -> None:
    state, results = run_trace(
        [
            {"op": "fund_miner", "miner": "m", "amount": 50},
            {"op": "open", "session_id": "da", "agent": "a", "miner": "m", "task_hash": "t", "model_hash": "m1", "payload_hash": "p", "decode_policy_hash": "d", "precision": "fp16", "backend": "b", "gpu_cell": "g", "prompt_hash": "ph", "input_hash": "ih", "toploc_root": "root", "da_reference": "da", "commitment": "activation", "escrow": 10, "reserved_collateral": 50, "declared_exposure": 10, "p_effective_lower_bound": 0.5},
            {"op": "turn", "session_id": "da", "index": 0, "task_hash": "t", "model_hash": "m1", "precision": "fp16", "backend": "b", "gpu_cell": "g", "prompt_hash": "ph", "input_hash": "ih", "toploc_root": "root", "activation_commitment": "activation", "da_reference": "da", "output_hash": "o", "commitment": {"derive": "turn"}, "gn": 1},
            {"op": "settle", "session_id": "da", "block": 1, "aggregate_gn": 1, "toploc_root": "root", "activation_commitment": "activation", "da_reference": "da"},
            {"op": "fund_challenger", "challenger": "a", "amount": 100},
            {"op": "challenge", "session_id": "da", "challenger": "a", "block": 2, "bond": 100, "da_available": False},
            {"op": "challenge", "session_id": "da", "challenger": "a", "block": 3, "bond": 100, "da_available": False},
        ]
    )
    assert results[-1].code == "DA_UNAVAILABLE_REFUND"
    assert state.challenger_bond_returned.get("a", 0) == 0
    assert state.challenger_available["a"] == 100


def test_multi_channel_exposure_is_aggregated() -> None:
    assert multi_channel_deterrence_margin([60, 70, 80], 0.5, 500) == pytest.approx(40)


def test_collectible_slash_is_capped_by_reserved_collateral() -> None:
    state, results = run_trace(
        [
            {"op": "fund_miner", "miner": "m", "amount": 50},
            {"op": "open", "session_id": "cap", "agent": "a", "miner": "m", "task_hash": "t-cap", "model_hash": "m1", "payload_hash": "p", "decode_policy_hash": "d", "precision": "fp16", "backend": "b", "gpu_cell": "g", "prompt_hash": "ph", "input_hash": "ih", "toploc_root": "root", "da_reference": "da", "commitment": "activation", "escrow": 100, "miner_collateral": 50, "reserved_collateral": 50, "declared_exposure": 20, "p_effective_lower_bound": 0.9},
            {"op": "turn", "session_id": "cap", "index": 0, "task_hash": "t-cap", "model_hash": "m1", "precision": "fp16", "backend": "b", "gpu_cell": "g", "prompt_hash": "ph", "input_hash": "ih", "toploc_root": "root", "activation_commitment": "activation", "da_reference": "da", "output_hash": "o", "commitment": {"derive": "turn"}, "gn": 1},
            {"op": "settle", "session_id": "cap", "block": 1, "aggregate_gn": 1, "toploc_root": "root", "activation_commitment": "activation", "da_reference": "da"},
            {"op": "fund_challenger", "challenger": "a", "amount": 100},
            {"op": "challenge", "session_id": "cap", "challenger": "a", "block": 2, "bond": 100},
            {"op": "respond", "session_id": "cap", "block": 3, "matches_commitment": False},
        ]
    )
    assert results[-1].effects["miner_slash"] == 50
    assert state.agent_refunds["a"] == 100
    assert escrow_conserved(state, "cap")
    assert collateral_conserved(state, "m")
    assert state.miner_collateral_slashed["m"] == 50
    assert state.challenger_available["a"] == 100
