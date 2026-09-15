"""Deterministic state transitions for a small non-consensus SOFT profile.

The model captures binding, replay protection, windows, standing, bonds, and
fail-closed data availability.  It deliberately uses booleans and strings in
place of signatures, Merkle proofs, and authenticated storage.  It is a
reference for proposed behavior, not production protocol or cryptographic
code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
from typing import Any, Iterable, Mapping


HARNESSED_BOUND_FIELDS = (
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
)


class SessionStatus(str, Enum):
    OPEN = "open"
    SETTLED = "settled"
    CHALLENGED = "challenged"
    FINALIZED = "finalized"
    FRAUD_UPHELD = "fraud_upheld"
    REFUNDED_DA = "refunded_da"
    REFUNDED_TIMEOUT = "refunded_timeout"


@dataclass(frozen=True)
class SoftConfig:
    profile: str = "flop-soft-v1"
    challenge_window_blocks: int = 100
    response_window_blocks: int = 20
    da_repair_extensions: int = 1
    challenger_bond: int = 100
    session_timeout_blocks: int = 200
    max_challenges: int = 2

    def __post_init__(self) -> None:
        for name in (
            "challenge_window_blocks",
            "response_window_blocks",
            "da_repair_extensions",
            "challenger_bond",
            "session_timeout_blocks",
            "max_challenges",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.challenge_window_blocks == 0:
            raise ValueError("challenge_window_blocks must be positive")
        if self.response_window_blocks == 0:
            raise ValueError("response_window_blocks must be positive")
        if self.max_challenges < 1:
            raise ValueError("max_challenges must be positive")


@dataclass(frozen=True)
class Turn:
    index: int
    task_hash: str
    model_hash: str
    payload_hash: str
    decode_policy_hash: str
    precision: str
    backend: str
    gpu_cell: str
    prompt_hash: str
    input_hash: str
    output_hash: str
    toploc_root: str
    activation_commitment: str
    da_reference: str
    nonce: int
    commitment: str
    gn: int
    miner_signed: bool = True
    agent_countersigned: bool = True


@dataclass
class Challenge:
    challenger: str
    turn_index: int | None
    bond: int
    opened_at: int
    response_deadline: int


@dataclass
class Session:
    session_id: str
    agent: str
    miner: str
    task_hash: str
    model_hash: str
    payload_hash: str
    decode_policy_hash: str
    precision: str
    backend: str
    gpu_cell: str
    prompt_hash: str
    input_hash: str
    profile: str
    toploc_root: str
    nonce: int
    activation_commitment: str
    da_reference: str
    escrow: int
    miner_collateral: int
    reserved_collateral: int
    started_at: int
    delivery_deadline: int
    challenge_deadline: int | None = None
    status: SessionStatus = SessionStatus.OPEN
    turns: list[Turn] = field(default_factory=list)
    aggregate_gn: int = 0
    paid: int = 0
    refunded: int = 0
    miner_slash: int = 0
    challenge: Challenge | None = None
    da_extensions: int = 0
    challenge_count: int = 0
    collateral_slashed: int = 0
    declared_exposure: float = 0.0
    p_effective_lower_bound: float = 0.0
    safety_margin: float = 0.0
    collectible_lower_bound: float = 0.0


@dataclass
class SoftState:
    """Mutable ledger state used by the pure-ish transition functions."""

    config: SoftConfig = field(default_factory=SoftConfig)
    sessions: dict[str, Session] = field(default_factory=dict)
    processed_tasks: set[str] = field(default_factory=set)
    credited_gn: dict[str, int] = field(default_factory=dict)
    miner_paid: dict[str, int] = field(default_factory=dict)
    agent_refunds: dict[str, int] = field(default_factory=dict)
    escrow_locked: dict[str, int] = field(default_factory=dict)
    escrow_paid: dict[str, int] = field(default_factory=dict)
    escrow_refunded: dict[str, int] = field(default_factory=dict)
    miner_collateral_available: dict[str, int] = field(default_factory=dict)
    miner_collateral_reserved: dict[str, int] = field(default_factory=dict)
    miner_collateral_deposited: dict[str, int] = field(default_factory=dict)
    miner_collateral_slashed: dict[str, int] = field(default_factory=dict)
    challenger_available: dict[str, int] = field(default_factory=dict)
    challenger_bond_locked: dict[str, int] = field(default_factory=dict)
    challenger_bond_returned: dict[str, int] = field(default_factory=dict)
    challenger_bond_forfeited: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class TransitionResult:
    accepted: bool
    code: str
    message: str
    state: SoftState
    session: Session | None = None
    effects: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.accepted


def _result(
    state: SoftState,
    accepted: bool,
    code: str,
    message: str,
    session: Session | None = None,
    **effects: Any,
) -> TransitionResult:
    return TransitionResult(accepted, code, message, state, session, effects)


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def make_task_hash(
    agent: str,
    nonce: int,
    model_hash: str,
    payload_hash: str,
    commitment: str,
) -> str:
    """Make a stable illustrative task identifier.

    The digest is for deterministic examples only; it is not a wire-format or
    security claim.
    """

    return hashlib.sha256(
        _canonical(
            {
                "agent": agent,
                "nonce": nonce,
                "model_hash": model_hash,
                "payload_hash": payload_hash,
                "commitment": commitment,
            }
        )
    ).hexdigest()


def make_commitment(
    session_id: str,
    profile: str,
    index: int,
    task_hash: str,
    model_hash: str,
    payload_hash: str,
    decode_policy_hash: str,
    precision: str,
    backend: str,
    gpu_cell: str,
    prompt_hash: str,
    input_hash: str,
    output_hash: str,
    gn: int,
    toploc_root: str,
    activation_commitment: str,
    da_reference: str,
    nonce: int,
) -> str:
    """Derive the per-turn commitment over every profile-bound field."""

    return hashlib.sha256(
        _canonical(
            {
                "session_id": session_id,
                "profile": profile,
                "index": index,
                "task_hash": task_hash,
                "model_hash": model_hash,
                "payload_hash": payload_hash,
                "decode_policy_hash": decode_policy_hash,
                "precision": precision,
                "backend": backend,
                "gpu_cell": gpu_cell,
                "prompt_hash": prompt_hash,
                "input_hash": input_hash,
                "output_hash": output_hash,
                "gn": gn,
                "toploc_root": toploc_root,
                "activation_commitment": activation_commitment,
                "da_reference": da_reference,
                "nonce": nonce,
            }
        )
    ).hexdigest()


make_turn_commitment = make_commitment
derive_turn_commitment = make_commitment


def open_session(
    state: SoftState,
    *,
    session_id: str,
    agent: str,
    miner: str,
    task_hash: str,
    model_hash: str,
    payload_hash: str,
    decode_policy_hash: str,
    escrow: int,
    precision: str = "",
    backend: str = "",
    gpu_cell: str = "",
    prompt_hash: str = "",
    input_hash: str = "",
    commitment: str | None = None,
    activation_commitment: str | None = None,
    miner_collateral: int | None = None,
    reserved_collateral: int = 0,
    profile: str | None = None,
    toploc_root: str = "",
    da_reference: str = "",
    nonce: int = 0,
    declared_exposure: float = 0.0,
    p_effective_lower_bound: float = 0.0,
    safety_margin: float | None = None,
    block: int = 0,
) -> TransitionResult:
    """Open one bounded SOFT session."""

    if commitment is not None and activation_commitment is not None and commitment != activation_commitment:
        return _result(state, False, "ACTIVATION_COMMITMENT_MISMATCH", "activation commitment declarations differ")
    if commitment is None:
        commitment = activation_commitment
    if session_id in state.sessions:
        return _result(state, False, "DUPLICATE_SESSION", "session_id already exists")
    if task_hash in state.processed_tasks:
        return _result(state, False, "DUPLICATE_CREDIT", "task_hash was already credited")
    if escrow < 0:
        return _result(state, False, "INVALID_ESCROW", "escrow cannot be negative")
    required_text = {
        "toploc_root": toploc_root,
        "activation_commitment": commitment,
        "da_reference": da_reference,
        "precision": precision,
        "backend": backend,
        "gpu_cell": gpu_cell,
        "prompt_hash": prompt_hash,
        "input_hash": input_hash,
    }
    missing = next((name for name, value in required_text.items() if not isinstance(value, str) or not value.strip()), None)
    if missing:
        return _result(state, False, f"MISSING_{missing.upper()}", f"{missing} is required at session open")
    if miner_collateral is not None and miner_collateral != state.miner_collateral_deposited.get(miner, 0):
        return _result(state, False, "COLLATERAL_DECLARATION_MISMATCH", "miner collateral must be pre-funded")
    if reserved_collateral < 0 or reserved_collateral > state.miner_collateral_available.get(miner, 0):
        return _result(state, False, "INSUFFICIENT_COLLATERAL", "reserved collateral is not available")
    try:
        declared_exposure = float(declared_exposure)
    except (TypeError, ValueError):
        return _result(state, False, "INVALID_EXPOSURE", "declared exposure must be finite and non-negative")
    if declared_exposure < 0 or not math.isfinite(declared_exposure):
        return _result(state, False, "INVALID_EXPOSURE", "declared exposure must be finite and non-negative")
    try:
        p_effective_lower_bound = float(p_effective_lower_bound)
    except (TypeError, ValueError):
        return _result(state, False, "INVALID_P_EFFECTIVE", "p_effective lower bound must be in (0, 1]")
    if not math.isfinite(p_effective_lower_bound) or not 0 < p_effective_lower_bound <= 1:
        return _result(state, False, "INVALID_P_EFFECTIVE", "p_effective lower bound must be in (0, 1]")
    active = (
        session
        for session in state.sessions.values()
        if session.miner == miner
        and session.status in {SessionStatus.OPEN, SessionStatus.SETTLED, SessionStatus.CHALLENGED}
    )
    aggregate_exposure = declared_exposure + sum(item.declared_exposure for item in active)
    b_col_lower = state.miner_collateral_reserved.get(miner, 0) + reserved_collateral
    pre_funded_net = (
        state.miner_collateral_deposited.get(miner, 0)
        - state.miner_collateral_slashed.get(miner, 0)
    )
    if b_col_lower > pre_funded_net:
        return _result(
            state,
            False,
            "INSUFFICIENT_BACKED_COLLATERAL",
            "reserved collectible collateral exceeds pre-funded, unslashed collateral",
        )
    effective_lower_bound = min(
        [p_effective_lower_bound]
        + [
            item.p_effective_lower_bound
            for item in state.sessions.values()
            if item.miner == miner
            and item.status in {SessionStatus.OPEN, SessionStatus.SETTLED, SessionStatus.CHALLENGED}
        ]
    )
    margin = effective_lower_bound * b_col_lower - aggregate_exposure
    if margin <= 0:
        return _result(
            state,
            False,
            "UNSAFE_AGGREGATE_EXPOSURE",
            "strict p_effective lower-bound times backed collateral does not cover aggregate exposure",
        )
    if safety_margin is not None:
        try:
            safety_margin = float(safety_margin)
        except (TypeError, ValueError):
            return _result(state, False, "INVALID_SAFETY_MARGIN", "safety margin must be finite and non-negative")
        if not math.isfinite(safety_margin) or safety_margin < 0 or safety_margin > margin:
            return _result(state, False, "SAFETY_MARGIN_UNMET", "declared safety margin exceeds measured margin")
    if nonce < 0:
        return _result(state, False, "INVALID_NONCE", "nonce cannot be negative")
    if block < 0:
        return _result(state, False, "INVALID_BLOCK", "block cannot be negative")
    session = Session(
        session_id=session_id,
        agent=agent,
        miner=miner,
        task_hash=task_hash,
        model_hash=model_hash,
        payload_hash=payload_hash,
        decode_policy_hash=decode_policy_hash,
        precision=precision,
        backend=backend,
        gpu_cell=gpu_cell,
        prompt_hash=prompt_hash,
        input_hash=input_hash,
        profile=profile or state.config.profile,
        toploc_root=toploc_root,
        nonce=nonce,
        activation_commitment=commitment,
        da_reference=da_reference,
        escrow=escrow,
        miner_collateral=(
            state.miner_collateral_deposited.get(miner, 0)
            if miner_collateral is None
            else miner_collateral
        ),
        reserved_collateral=reserved_collateral,
        started_at=block,
        delivery_deadline=block + state.config.session_timeout_blocks,
        declared_exposure=float(declared_exposure),
        p_effective_lower_bound=float(p_effective_lower_bound),
        safety_margin=float(margin),
        collectible_lower_bound=float(reserved_collateral),
    )
    state.sessions[session_id] = session
    state.escrow_locked[session_id] = escrow
    state.miner_collateral_reserved[miner] = (
        state.miner_collateral_reserved.get(miner, 0) + reserved_collateral
    )
    state.miner_collateral_available[miner] = (
        state.miner_collateral_available.get(miner, 0) - reserved_collateral
    )
    return _result(
        state,
        True,
        "OPENED",
        "session opened",
        session,
        escrow_locked=escrow,
        miner_collateral=session.miner_collateral,
        reserved_collateral=reserved_collateral,
        declared_exposure=declared_exposure,
        p_effective_lower_bound=p_effective_lower_bound,
        b_col_lower=b_col_lower,
        safety_margin=margin,
    )


def append_turn(
    state: SoftState,
    *,
    session_id: str,
    index: int,
    task_hash: str,
    model_hash: str,
    output_hash: str,
    gn: int,
    commitment: str,
    payload_hash: str | None = None,
    decode_policy_hash: str | None = None,
    precision: str | None = None,
    backend: str | None = None,
    gpu_cell: str | None = None,
    prompt_hash: str | None = None,
    input_hash: str | None = None,
    toploc_root: str | None = None,
    activation_commitment: str | None = None,
    da_reference: str | None = None,
    nonce: int | None = None,
    miner_signed: bool = True,
    agent_countersigned: bool = True,
) -> TransitionResult:
    """Append one co-signed turn, enforcing binding and monotonic uniqueness."""

    session = state.sessions.get(session_id)
    if session is None:
        return _result(state, False, "UNKNOWN_SESSION", "session_id does not exist")
    if session.status is not SessionStatus.OPEN:
        return _result(state, False, "SESSION_NOT_OPEN", "turns are accepted only while open", session)
    if index != len(session.turns):
        return _result(state, False, "TURN_INDEX", "turn_index must be the next monotonic index", session)
    if task_hash != session.task_hash:
        return _result(state, False, "TASK_BINDING_MISMATCH", "turn task_hash differs from session", session)
    if model_hash != session.model_hash:
        return _result(state, False, "MODEL_BINDING_MISMATCH", "turn model_hash differs from session", session)
    payload_hash = session.payload_hash if payload_hash is None else payload_hash
    decode_policy_hash = session.decode_policy_hash if decode_policy_hash is None else decode_policy_hash
    if precision is None:
        return _result(state, False, "MISSING_PRECISION", "precision is required on every turn", session)
    if backend is None:
        return _result(state, False, "MISSING_BACKEND", "backend is required on every turn", session)
    if gpu_cell is None:
        return _result(state, False, "MISSING_GPU_CELL", "GPU cell is required on every turn", session)
    if prompt_hash is None:
        return _result(state, False, "MISSING_PROMPT_HASH", "prompt hash is required on every turn", session)
    if input_hash is None:
        return _result(state, False, "MISSING_INPUT_HASH", "input hash is required on every turn", session)
    if toploc_root is None:
        return _result(state, False, "MISSING_TOPLOC_ROOT", "TOPLOC root is required on every turn", session)
    if activation_commitment is None:
        return _result(state, False, "MISSING_ACTIVATION_COMMITMENT", "activation commitment is required on every turn", session)
    if da_reference is None:
        return _result(state, False, "MISSING_DA_REFERENCE", "DA reference is required on every turn", session)
    nonce = session.nonce if nonce is None else nonce
    if nonce < 0:
        return _result(state, False, "INVALID_NONCE", "nonce cannot be negative", session)
    if not output_hash:
        return _result(state, False, "MISSING_OUTPUT_HASH", "turn output_hash is required", session)
    if payload_hash != session.payload_hash:
        return _result(state, False, "PAYLOAD_BINDING_MISMATCH", "turn payload_hash differs from session", session)
    if decode_policy_hash != session.decode_policy_hash:
        return _result(state, False, "DECODE_BINDING_MISMATCH", "turn decode policy differs from session", session)
    bindings = {
        "precision": precision,
        "backend": backend,
        "gpu_cell": gpu_cell,
        "prompt_hash": prompt_hash,
        "input_hash": input_hash,
        "toploc_root": toploc_root,
        "activation_commitment": activation_commitment,
        "da_reference": da_reference,
    }
    missing = next((name for name, value in bindings.items() if not isinstance(value, str) or not value.strip()), None)
    if missing:
        return _result(state, False, f"MISSING_{missing.upper()}", f"{missing} must be non-empty", session)
    if precision != session.precision:
        return _result(state, False, "PRECISION_BINDING_MISMATCH", "precision differs from session", session)
    if backend != session.backend:
        return _result(state, False, "BACKEND_BINDING_MISMATCH", "backend differs from session", session)
    if gpu_cell != session.gpu_cell:
        return _result(state, False, "GPU_CELL_BINDING_MISMATCH", "GPU cell differs from session", session)
    if prompt_hash != session.prompt_hash:
        return _result(state, False, "PROMPT_BINDING_MISMATCH", "prompt hash differs from session", session)
    if input_hash != session.input_hash:
        return _result(state, False, "INPUT_BINDING_MISMATCH", "input hash differs from session", session)
    if toploc_root != session.toploc_root:
        return _result(state, False, "TOPLOC_BINDING_MISMATCH", "turn TOPLOC root differs from session", session)
    if activation_commitment != session.activation_commitment:
        return _result(state, False, "ACTIVATION_BINDING_MISMATCH", "activation commitment differs from session", session)
    if da_reference != session.da_reference:
        return _result(state, False, "DA_BINDING_MISMATCH", "DA reference differs from session", session)
    if gn < 0:
        return _result(state, False, "INVALID_GN", "gn cannot be negative", session)
    if not miner_signed or not agent_countersigned:
        return _result(state, False, "MISSING_RECEIPT_SIGNATURE", "both illustrative signatures are required", session)
    expected_commitment = make_commitment(
        session_id=session.session_id,
        profile=session.profile,
        index=index,
        task_hash=task_hash,
        model_hash=model_hash,
        payload_hash=payload_hash,
        decode_policy_hash=decode_policy_hash,
        precision=precision,
        backend=backend,
        gpu_cell=gpu_cell,
        prompt_hash=prompt_hash,
        input_hash=input_hash,
        output_hash=output_hash,
        gn=gn,
        toploc_root=toploc_root,
        activation_commitment=activation_commitment,
        da_reference=da_reference,
        nonce=nonce,
    )
    if commitment != expected_commitment:
        return _result(
            state,
            False,
            "DERIVED_COMMITMENT_MISMATCH",
            "commitment is not the derivation of every bound turn field",
            session,
        )
    session.turns.append(
        Turn(
            index,
            task_hash,
            model_hash,
            payload_hash,
            decode_policy_hash,
            precision,
            backend,
            gpu_cell,
            prompt_hash,
            input_hash,
            output_hash,
            toploc_root,
            activation_commitment,
            da_reference,
            nonce,
            commitment,
            gn,
            miner_signed,
            agent_countersigned,
        )
    )
    return _result(state, True, "TURN_ACCEPTED", "turn appended", session, turn_index=index)


def _release_collateral(state: SoftState, session: Session, slash: int = 0) -> int:
    """Release a session reservation, returning only the collectible remainder."""

    available_reservation = session.reserved_collateral - session.collateral_slashed
    slash = min(max(slash, 0), max(available_reservation, 0))
    remaining = available_reservation - slash
    reserved = state.miner_collateral_reserved.get(session.miner, 0) - session.reserved_collateral
    state.miner_collateral_reserved[session.miner] = max(reserved, 0)
    state.miner_collateral_available[session.miner] = (
        state.miner_collateral_available.get(session.miner, 0) + remaining
    )
    if slash:
        state.miner_collateral_slashed[session.miner] = (
            state.miner_collateral_slashed.get(session.miner, 0) + slash
        )
        session.collateral_slashed += slash
    return slash


def _reverse_settlement(state: SoftState, session: Session) -> None:
    state.processed_tasks.discard(session.task_hash)
    prior = state.credited_gn.get(session.miner, 0) - session.aggregate_gn
    if prior:
        state.credited_gn[session.miner] = prior
    else:
        state.credited_gn.pop(session.miner, None)
    paid = state.miner_paid.get(session.miner, 0) - session.paid
    if paid:
        state.miner_paid[session.miner] = paid
    else:
        state.miner_paid.pop(session.miner, None)
    if session.session_id in state.escrow_paid:
        state.escrow_paid.pop(session.session_id)
        state.escrow_refunded[session.session_id] = session.escrow


def escrow_conserved(state: SoftState, session_id: str) -> bool:
    """Check that one session's escrow is in exactly one lifecycle bucket."""

    session = state.sessions[session_id]
    total = (
        state.escrow_locked.get(session_id, 0)
        + state.escrow_paid.get(session_id, 0)
        + state.escrow_refunded.get(session_id, 0)
    )
    return total == session.escrow


def collateral_conserved(state: SoftState, miner: str) -> bool:
    """Check deposited miner collateral equals available + reserved + slashed."""

    return state.miner_collateral_deposited.get(miner, 0) == (
        state.miner_collateral_available.get(miner, 0)
        + state.miner_collateral_reserved.get(miner, 0)
        + state.miner_collateral_slashed.get(miner, 0)
    )


def fund_challenger(state: SoftState, *, challenger: str, amount: int) -> TransitionResult:
    """Add illustrative available balance used to post challenge bonds."""

    if amount < 0:
        return _result(state, False, "INVALID_BALANCE", "balance funding cannot be negative")
    state.challenger_available[challenger] = state.challenger_available.get(challenger, 0) + amount
    return _result(state, True, "CHALLENGER_FUNDED", "challenger balance funded", None, available=amount)


def fund_miner_collateral(state: SoftState, *, miner: str, amount: int) -> TransitionResult:
    """Pre-fund one shared miner collateral account.

    Opening a session only moves this balance into a reservation; it never
    creates another deposit, preventing concurrent channels from double-counting
    the same collateral.
    """

    if amount < 0:
        return _result(state, False, "INVALID_COLLATERAL", "collateral funding cannot be negative")
    state.miner_collateral_deposited[miner] = state.miner_collateral_deposited.get(miner, 0) + amount
    state.miner_collateral_available[miner] = state.miner_collateral_available.get(miner, 0) + amount
    return _result(state, True, "MINER_COLLATERAL_FUNDED", "miner collateral pre-funded", None, available=amount)


def settle_session(
    state: SoftState,
    *,
    session_id: str,
    block: int,
    aggregate_gn: int,
    toploc_root: str | None = None,
    activation_commitment: str | None = None,
    da_reference: str | None = None,
) -> TransitionResult:
    """Credit a co-signed claim optimistically, opening its challenge window."""

    session = state.sessions.get(session_id)
    if session is None:
        return _result(state, False, "UNKNOWN_SESSION", "session_id does not exist")
    if session.status is not SessionStatus.OPEN:
        return _result(state, False, "SESSION_NOT_SETTLEABLE", "session is not open", session)
    if not session.turns:
        return _result(state, False, "NO_TURNS", "a session needs at least one turn", session)
    if toploc_root is None:
        return _result(state, False, "MISSING_TOPLOC_ROOT", "TOPLOC root is required at settlement", session)
    if activation_commitment is None:
        return _result(state, False, "MISSING_ACTIVATION_COMMITMENT", "activation commitment is required at settlement", session)
    if da_reference is None:
        return _result(state, False, "MISSING_DA_REFERENCE", "DA reference is required at settlement", session)
    if not toploc_root.strip():
        return _result(state, False, "MISSING_TOPLOC_ROOT", "TOPLOC root must be non-empty", session)
    if not activation_commitment.strip():
        return _result(state, False, "MISSING_ACTIVATION_COMMITMENT", "activation commitment must be non-empty", session)
    if not da_reference.strip():
        return _result(state, False, "MISSING_DA_REFERENCE", "DA reference must be non-empty", session)
    if toploc_root != session.toploc_root:
        return _result(state, False, "TOPLOC_BINDING_MISMATCH", "settlement TOPLOC root differs from session", session)
    if activation_commitment != session.activation_commitment:
        return _result(state, False, "ACTIVATION_BINDING_MISMATCH", "settlement activation commitment differs from session", session)
    if da_reference != session.da_reference:
        return _result(state, False, "DA_BINDING_MISMATCH", "settlement DA reference differs from session", session)
    if block < session.started_at:
        return _result(state, False, "INVALID_BLOCK", "settlement precedes session opening", session)
    if aggregate_gn != sum(turn.gn for turn in session.turns):
        return _result(state, False, "GN_SUM_MISMATCH", "aggregate_gn does not equal signed turns", session)
    if aggregate_gn < 0:
        return _result(state, False, "INVALID_GN", "aggregate_gn cannot be negative", session)
    if session.task_hash in state.processed_tasks:
        return _result(state, False, "DUPLICATE_CREDIT", "task_hash was already credited", session)
    state.processed_tasks.add(session.task_hash)
    session.aggregate_gn = aggregate_gn
    session.paid = session.escrow
    session.status = SessionStatus.SETTLED
    session.challenge_deadline = block + state.config.challenge_window_blocks
    state.credited_gn[session.miner] = state.credited_gn.get(session.miner, 0) + aggregate_gn
    state.miner_paid[session.miner] = state.miner_paid.get(session.miner, 0) + session.escrow
    state.escrow_locked.pop(session_id, None)
    state.escrow_paid[session_id] = session.escrow
    return _result(
        state,
        True,
        "SETTLED",
        "optimistic settlement accepted",
        session,
        credited_gn=aggregate_gn,
        paid=session.escrow,
        challenge_deadline=session.challenge_deadline,
    )


def challenge_session(
    state: SoftState,
    *,
    session_id: str,
    challenger: str,
    block: int,
    bond: int,
    da_available: bool = True,
) -> TransitionResult:
    """Open a standing challenge, or apply the one-time DA repair policy."""

    session = state.sessions.get(session_id)
    if session is None:
        return _result(state, False, "UNKNOWN_SESSION", "session_id does not exist")
    if session.status is not SessionStatus.SETTLED:
        return _result(state, False, "NOT_CHALLENGEABLE", "only settled/provisional sessions can be challenged", session)
    if session.challenge_count >= state.config.max_challenges:
        return _result(state, False, "CHALLENGE_LIMIT", "the session has used its challenge attempts", session)
    if session.challenge_deadline is None or block > session.challenge_deadline:
        return _result(state, False, "CHALLENGE_WINDOW_CLOSED", "challenge arrived after the window", session)
    if challenger != session.agent and not challenger.startswith("validator:"):
        return _result(state, False, "NO_STANDING", "only the session agent or active validator may challenge", session)
    if bond != state.config.challenger_bond:
        return _result(
            state,
            False,
            "BOND_REQUIRED",
            "the exact challenger bond is required before lock",
            session,
            bond_locked=0,
        )
    if not da_available:
        if session.da_extensions < state.config.da_repair_extensions:
            session.da_extensions += 1
            session.challenge_deadline += state.config.challenge_window_blocks
            return _result(
                state,
                True,
                "DA_WINDOW_EXTENDED",
                "temporary DA loss extends the window once without payout or slash",
                session,
                bond_locked=0,
                challenge_deadline=session.challenge_deadline,
            )
        _reverse_settlement(state, session)
        session.status = SessionStatus.REFUNDED_DA
        session.refunded = session.escrow
        _release_collateral(state, session)
        state.agent_refunds[session.agent] = state.agent_refunds.get(session.agent, 0) + session.escrow
        return _result(
            state,
            True,
            "DA_UNAVAILABLE_REFUND",
            "unrecoverable DA fails closed and refunds escrow",
            session,
            bond_locked=0,
            bond_returned=0,
            miner_slash=0,
            refund=session.escrow,
        )
    if state.challenger_available.get(challenger, 0) < bond:
        return _result(
            state,
            False,
            "INSUFFICIENT_BOND_BALANCE",
            "challenger does not have an available bond balance",
            session,
            bond_locked=0,
        )
    session.challenge = Challenge(
        challenger,
        None,
        bond,
        block,
        block + state.config.response_window_blocks,
    )
    session.status = SessionStatus.CHALLENGED
    session.challenge_count += 1
    state.challenger_available[challenger] -= bond
    state.challenger_bond_locked[challenger] = state.challenger_bond_locked.get(challenger, 0) + bond
    return _result(
        state,
        True,
        "CHALLENGE_OPENED",
        "challenge bond locked",
        session,
        bond_locked=bond,
        response_deadline=session.challenge.response_deadline,
    )


def _fraud_upheld(state: SoftState, session: Session, reason: str) -> TransitionResult:
    _reverse_settlement(state, session)
    session.status = SessionStatus.FRAUD_UPHELD
    # Fraud may collect the session's entire reserved collectible capacity.
    # It is deliberately not capped by optimistic escrow/payment: the
    # admission bound is backed by this exact per-session reservation.
    session.miner_slash = max(session.collectible_lower_bound - session.collateral_slashed, 0)
    _release_collateral(state, session, session.miner_slash)
    session.refunded = session.escrow
    state.agent_refunds[session.agent] = state.agent_refunds.get(session.agent, 0) + session.escrow
    if session.challenge is not None:
        challenger = session.challenge.challenger
        bond = session.challenge.bond
        state.challenger_bond_returned[challenger] = state.challenger_bond_returned.get(challenger, 0) + bond
        state.challenger_bond_locked[challenger] -= bond
        state.challenger_available[challenger] = state.challenger_available.get(challenger, 0) + bond
    return _result(
        state,
        True,
        "FRAUD_UPHELD",
        reason,
        session,
        miner_slash=session.miner_slash,
        collectible_slash=session.miner_slash,
        b_col_lower=session.collectible_lower_bound,
        refund=session.refunded,
        bond_returned=session.challenge.bond if session.challenge else 0,
    )


def respond_to_challenge(
    state: SoftState,
    *,
    session_id: str,
    block: int,
    matches_commitment: bool,
) -> TransitionResult:
    """Dismiss a valid claim or uphold a mismatch in the challenged turn."""

    session = state.sessions.get(session_id)
    if session is None:
        return _result(state, False, "UNKNOWN_SESSION", "session_id does not exist")
    if session.status is not SessionStatus.CHALLENGED or session.challenge is None:
        return _result(state, False, "NO_OPEN_CHALLENGE", "there is no open challenge", session)
    if block > session.challenge.response_deadline:
        return _result(state, False, "RESPONSE_WINDOW_CLOSED", "response requires timeout after its deadline", session)
    challenger = session.challenge.challenger
    bond = session.challenge.bond
    if matches_commitment:
        session.status = SessionStatus.SETTLED
        state.challenger_bond_locked[challenger] -= bond
        state.challenger_bond_forfeited[challenger] = state.challenger_bond_forfeited.get(challenger, 0) + bond
        session.challenge = None
        return _result(
            state,
            True,
            "DISMISSED",
            "honest response matched the session commitment; claim remains provisional",
            session,
            bond_forfeited=bond,
            status_after=session.status.value,
        )
    return _fraud_upheld(state, session, "response exposed a commitment mismatch")


def timeout_session(
    state: SoftState,
    *,
    session_id: str,
    block: int,
) -> TransitionResult:
    """Resolve a response timeout, challenge expiry, or non-delivery timeout."""

    session = state.sessions.get(session_id)
    if session is None:
        return _result(state, False, "UNKNOWN_SESSION", "session_id does not exist")
    if session.status is SessionStatus.CHALLENGED and session.challenge is not None:
        if block <= session.challenge.response_deadline:
            return _result(state, False, "TIMEOUT_TOO_EARLY", "response window is still open", session)
        return _fraud_upheld(state, session, "challenge response timed out; fraud is the default")
    if session.status is SessionStatus.SETTLED:
        if session.challenge_deadline is None or block <= session.challenge_deadline:
            return _result(state, False, "TIMEOUT_TOO_EARLY", "challenge window is still open", session)
        session.status = SessionStatus.FINALIZED
        _release_collateral(state, session)
        return _result(state, True, "FINALIZED", "challenge window elapsed", session)
    if session.status is SessionStatus.OPEN:
        if block <= session.delivery_deadline:
            return _result(state, False, "TIMEOUT_TOO_EARLY", "delivery deadline is still open", session)
        session.status = SessionStatus.REFUNDED_TIMEOUT
        session.refunded = session.escrow
        state.escrow_locked.pop(session_id, None)
        state.escrow_refunded[session_id] = session.escrow
        _release_collateral(state, session)
        state.agent_refunds[session.agent] = state.agent_refunds.get(session.agent, 0) + session.escrow
        return _result(
            state,
            True,
            "NON_DELIVERY_REFUND",
            "non-delivery timeout refunds escrow",
            session,
            refund=session.escrow,
        )
    return _result(state, False, "SESSION_RESOLVED", "session is already resolved", session)


def apply_event(state: SoftState, event: Mapping[str, Any]) -> TransitionResult:
    """Apply one JSON-friendly trace event."""

    operation = event.get("op")
    args = {key: value for key, value in event.items() if key != "op"}
    if operation == "fund_challenger":
        return fund_challenger(state, **args)
    if operation == "fund_miner":
        return fund_miner_collateral(state, **args)
    if operation == "turn" and isinstance(args.get("commitment"), Mapping):
        if args["commitment"].get("derive") != "turn":
            return _result(state, False, "UNKNOWN_COMMITMENT_BUILDER", "unsupported commitment builder")
        session = state.sessions.get(args.get("session_id"))
        if session is None:
            return _result(state, False, "UNKNOWN_SESSION", "session_id does not exist")
        index = args["index"]
        task_hash = args["task_hash"]
        model_hash = args["model_hash"]
        payload_hash = args.get("payload_hash", session.payload_hash)
        decode_policy_hash = args.get("decode_policy_hash", session.decode_policy_hash)
        precision = args.get("precision")
        backend = args.get("backend")
        gpu_cell = args.get("gpu_cell")
        prompt_hash = args.get("prompt_hash")
        input_hash = args.get("input_hash")
        output_hash = args["output_hash"]
        gn = args["gn"]
        toploc_root = args.get("toploc_root")
        activation_commitment = args.get("activation_commitment")
        da_reference = args.get("da_reference")
        nonce = args.get("nonce", session.nonce)
        args["commitment"] = make_commitment(
            session_id=session.session_id,
            profile=session.profile,
            index=index,
            task_hash=task_hash,
            model_hash=model_hash,
            payload_hash=payload_hash,
            decode_policy_hash=decode_policy_hash,
            precision=precision,
            backend=backend,
            gpu_cell=gpu_cell,
            prompt_hash=prompt_hash,
            input_hash=input_hash,
            output_hash=output_hash,
            gn=gn,
            toploc_root=toploc_root,
            activation_commitment=activation_commitment,
            da_reference=da_reference,
            nonce=nonce,
        )
        args.update(
            payload_hash=payload_hash,
            decode_policy_hash=decode_policy_hash,
            precision=precision,
            backend=backend,
            gpu_cell=gpu_cell,
            prompt_hash=prompt_hash,
            input_hash=input_hash,
            toploc_root=toploc_root,
            activation_commitment=activation_commitment,
            da_reference=da_reference,
            nonce=nonce,
        )
    functions = {
        "open": open_session,
        "turn": append_turn,
        "settle": settle_session,
        "challenge": challenge_session,
        "respond": respond_to_challenge,
        "timeout": timeout_session,
    }
    if operation not in functions:
        return _result(state, False, "UNKNOWN_OPERATION", f"unsupported operation: {operation}")
    return functions[operation](state, **args)


def run_trace(
    trace: Iterable[Mapping[str, Any]],
    *,
    config: SoftConfig | None = None,
) -> tuple[SoftState, list[TransitionResult]]:
    """Execute a vector trace and return final state plus every result."""

    state = SoftState(config=config or SoftConfig())
    results: list[TransitionResult] = []
    for event in trace:
        results.append(apply_event(state, event))
    return state, results
