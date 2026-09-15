# Proposed SOFT Verification Profile

**Status: research proposal; NON-AUTHORITATIVE.** This document does not amend,
replace, or claim conformance with the FLOP Network yellowpaper. It is a concrete
profile for discussion and implementation experiments. An implementation MUST
label this profile as `flop-soft-v1` and MUST NOT present a profile result as
HARD-tier or as an upstream protocol guarantee.

The source being profiled is the v0.5.0 `main` yellowpaper:
[yellowpaper.md](https://github.com/flop-labs/yellowpaper/blob/main/yellowpaper.md),
especially [§3.4](https://github.com/flop-labs/yellowpaper/blob/main/yellowpaper.md#34-tier-2--toploc-activation-commitments-mandatory-floor),
[§3.5](https://github.com/flop-labs/yellowpaper/blob/main/yellowpaper.md#35-tier-3--independent-optimistic-re-execution--slashing),
[§12.1](https://github.com/flop-labs/yellowpaper/blob/main/yellowpaper.md#121-sessions--attested-streaming--aggregate-settlement),
and requirements R3.1–R3.6 in §3.1. The source explicitly leaves the SOFT
definition and its commitment/opening bridge unresolved in E.33, E.43, E.44,
and E.45. The choices below are therefore proposals, not quotations from or
changes to that specification.

## 1. Purpose and conformance language

The SOFT tier is a non-TEE service class. It permits a miner without a TEE
quote or measured-SKU evidence to serve a session while retaining a
TEE-independent execution-integrity floor. “MUST”, “MUST NOT”, “REQUIRED”,
“SHOULD”, “SHOULD NOT”, and “MAY” have the meanings commonly assigned by
RFC 2119. A profile implementation MUST fail closed when a required item is
missing or ambiguous; it MUST NOT silently downgrade a failed SOFT check into
an ordinary paid result.

This profile verifies protocol claims (binding, arithmetic, availability, and
execution disagreement), not whether an answer is useful, safe, or correct for
the user’s purpose. It is intentionally conservative: a successful receipt is
initially *provisional work credit* until its challenge window expires.

## 2. Actors and proposed parameters

* **Agent** opens and funds a channel, checks each receipt, and is a standing
  challenger for its own channel.
* **SOFT miner** executes the model, signs turns with a session key, publishes
  commitments/evidence, and locks collectible collateral. The session key is
  not an attestation of hardware.
* **Checker** is an independently selected, calibrated miner identity. It MUST
  use a different registered hardware fingerprint and trust domain from the
  SOFT miner. It re-executes a challenged turn.
* **Validator** records DA references, samples checkers, verifies evidence and
  signatures, and supplies the quorum verdict. An active validator is also a
  standing challenger for any channel.
* **DA service** stores encrypted openings and public commitments outside the
  miner’s sole custody. DA is storage and retrieval infrastructure, not an
  execution oracle.
* **Settlement/runtime** enforces state transitions, replay protection, escrow,
  bonds, finality, and slashing.

The following are profile defaults, expressed in protocol units and thus
auditable rather than operator-local settings:

| Parameter | Profile-0.1 proposal |
| --- | --- |
| SOFT spot-check probability | `25,000 ppm` per eligible turn (1 in 40), matching the yellowpaper’s current `soft_tier_spot_check_rate_ppm` placeholder |
| checker committee | three checkers, stake-weighted VRF selection, pairwise-distinct fingerprints |
| challenger bond | `100 FLOP`, returned on an upheld challenge and forfeited on a dismissed one |
| response deadline | `7,200` blocks (approximately 2 hours) |
| challenge window | `604,800` blocks (7 days), never longer than DA retention |
| DA retention | at least `1,209,600` blocks (14 days) |
| escalation deadline | `7,200` blocks; a middle-band result cannot silently accept |
| collectible collateral | Miner-wide reserve satisfying both collectibility and the E.45 deterrence inequality over aggregate concurrent exposure; no fixed percentage is proposed |

The numerical values are proposed defaults only. Governance MUST ratify them,
the conversion from blocks to wall-clock time, and the collateral waterfall
before a production deployment.

## 3. Commitments and evidence

At `open_channel`, the miner MUST register `flop-soft-v1`, a calibrated
cell identifier `(model, precision, backend, GPU)`, a fresh session public key,
the channel’s value cap, and a commitment to the decode policy. Entry requires a
successful verified calibration burst and stake; it MUST NOT require a TEE
quote. A calibration label MUST be visible to the agent and priced separately
from HARD service.

For every turn `i`, before its output is accepted, the miner MUST commit to a
leaf containing:

`H(profile_id || session_id || turn_index || task_hash || model_hash ||
precision || backend || GPU-cell || prompt_hash || decode_policy_hash ||
input_hash || output_hash || G_n || TOPLOC_root || nonce)`.

The miner MUST also publish a TOPLOC activation commitment over the turn’s
activation transcript. TOPLOC commitments and DA references MUST be assigned
before challenge randomness is known. The commitment MUST bind the challenged
activation vector; an opening MUST be checked against the exact commitment and
not merely against a newly supplied vector. This implements the safety
precondition in §3.4/R3.4a without asserting that the precondition itself is a
cryptographic detection proof.

The miner signs `(session_id, turn_index, input_hash, output_hash, G_n,
leaf_hash)` with the session key. The agent verifies it and counter-signs a
running Merkle root. A receipt MUST bind the final root, aggregate `G_n`, and
the session profile. Duplicate indices, gaps, root mismatches, integer
overflow, or a `task_hash` already in `ProcessedTasks` MUST reject settlement.
These receipts prove agreement and arithmetic; they do not, by themselves,
prove execution correctness, consistent with §12.1(b).

Public evidence SHOULD contain hashes, roots, signatures, cell identifiers,
VRF proofs, verdicts, and DA content addresses. Prompt, output, activation
values, and model-derived material SHOULD be encrypted to the assigned
checker set. The encryption envelope MUST be bound to the leaf and challenge
nonce, and key release MUST occur only after a valid challenge assignment.
The profile provides no confidentiality against all assigned checkers, DA
operators, or a compromised endpoint; agents MUST disclose this privacy
boundary.

## 4. State machine and deadlines

The canonical states are:

`PROPOSED → OPEN → STREAMING → COMMITTED → PROVISIONAL → FINAL`

with side paths:

`PROVISIONAL → CHALLENGED → REEXECUTING → (FINAL | ESCALATED)`

and terminal failure paths:

`(OPEN | STREAMING | PROVISIONAL | CHALLENGED | ESCALATED) → REFUNDED`,
`REEXECUTING → SLASHED`, or `* → EXPIRED`.

1. **OPEN.** After finalized inclusion of `open_channel`, escrow, collateral,
   profile, cell, and session-key commitment are locked. The runtime MUST refuse
   a SOFT channel with a missing calibration or an unapproved value cap.
2. **STREAMING/COMMITTED.** Each output is deliverable only with a valid
   miner signature, agent counter-signature, monotonically unique index, leaf,
   TOPLOC reference, and DA publication receipt. Missing evidence makes the
   affected turn ineligible, not implicitly valid.
3. **PROVISIONAL.** `settle` verifies the complete submitted root and sum,
   pays the reserved escrow as required by the session tariff, and records
   public work credit as provisional. Under-use MUST NOT be refunded on the
   cooperative path. A force-close or non-delivery follows the §12.1(d)
   refund/penalty rules rather than inventing a SOFT success.
4. **CHALLENGED.** Only the session agent or an active validator MAY open a
   dispute. The challenger locks the bond and identifies one turn, one
   predicate, and one evidence reference. The runtime MUST reject arbitrary
   public challengers before bond lock.
5. **REEXECUTING/ESCALATED.** Checkers retrieve the encrypted opening and
   independently rerun the claimed input under the committed model, precision,
   backend, and decode policy. A quorum verifies assignment, checker bonds,
   signatures, commitment opening, and unanimity. A checker MUST NOT be the
   session miner, its account, or its fingerprint.
6. **FINAL/REFUNDED/SLASHED.** Finality is permitted only after the challenge
   window and finalized-head deadline. If DA is unavailable, the session MUST
   fail closed with refund and returned challenger bond, not a fraud slash.
   Finalized deadlines MUST freeze while consensus finality stalls; funds MUST
   never release from an unfinalized best head.

## 5. Challenge selection and re-execution

At each finalized block after a turn commitment, the runtime derives a
challenge ticket from epoch randomness, channel ID, turn index, and commitment
hash. Randomness MUST be fixed after the commitment and MUST NOT be selected
by the miner. A ticket below the `25,000 ppm` threshold selects the turn;
validators MAY additionally force a challenge for a high-value session or
when an evidence predicate fails. The selection transcript and VRF proof MUST
be public, so an operator cannot claim that an unobserved audit occurred.

The checker assignment MUST be stake-weighted VRF sampling from calibrated
identities, excluding the SOFT miner and its fingerprint, with three
pairwise-distinct fingerprints. The assignment, checker bonds, profile
version, and challenge nonce MUST be committed before openings are revealed.
The miner MUST provide the opening within the response deadline. It MUST
include the TOPLOC path, input and output material needed for deterministic
re-execution, model/decode identifiers, and a reproducible `G_n` witness.

Each checker returns `MATCH`, `MISMATCH`, or `UNAVAILABLE`, signed over the
challenge tuple. `MATCH` requires commitment membership, exact bound-field
equality, and the output/activation result within the calibrated cell’s
accepted band. `MISMATCH` is a protocol-fraud finding only: wrong model or
precision, invalid TOPLOC opening, forged signature, inflated `G_n`, root
inconsistency, or non-delivery. It MUST NOT be a verdict about answer quality.
`UNAVAILABLE` triggers DA repair/retrieval, not automatic fraud.

A unanimous checker result is not immediately final. During the remaining
challenge window, a standing challenger MAY request one fresh, disjoint
checker assignment. The fresh committee MUST verify the first assignment and
the second committee’s evidence. An overturned checker forfeits its bond. A
middle-band TOPLOC result MUST enter `ESCALATED`; within the escalation
deadline a quorum MUST issue `CLEAR` or `MISMATCH`. Escalation timeout is
inconclusive: the disputed work receives no final public credit, the agent
receives the corresponding withheld amount, and no miner fraud slash occurs
unless the timeout was caused by proven non-response.

## 6. Settlement and slashing outcomes

An upheld `MISMATCH`, forged receipt, or miner non-response MUST mark the
affected session fraudulent, refund the agent for the disputed/unverifiable
portion, and slash no more than the amount lawfully reserved and collectible
for that session. Admission MUST additionally enforce the economic model's
miner-wide condition over aggregate concurrent exposure; a per-session cap
alone is insufficient. The slash MUST be routed according to a ratified
waterfall; this profile proposes 70% to the agent, 20% to the checker/validator
evidence pool, and 10% burned. A repeated fraud MAY suspend the calibration
cell, but this profile does not authorize automatic global blacklisting.

A challenge dismissed after an honest matching response forfeits the challenger
bond to the evidence pool and preserves provisional settlement, matching the
published anti-griefing treatment. A malformed, duplicated, or out-of-standing
request MUST reject before any bond is locked. A DA repair failure refunds
escrow and returns any already-locked bond without asserting fraud. Public work
credit MUST be removed or marked non-qualifying after an upheld fraud verdict,
including credit already represented in an aggregate root; downstream reward
recovery MUST be atomic or explicitly record an unrecoverable debt.

## 7. Anti-griefing, privacy, and availability

The bond, standing restriction, one-open-dispute-per-turn rule, duplicate
challenge rejection, and checker accountability limit cheap disputes. A
challenger MUST identify a checkable predicate and supply a DA reference;
“the answer is bad” is invalid. The agent MUST NOT be charged for a
miner-caused DA outage. Concurrent channels MUST count toward the miner’s
collateral exposure; per-channel collateral alone is insufficient.

DA MUST be replicated across independent validator failure domains, retain
evidence through the entire seven-day challenge window plus repair margin, and
expose availability receipts. Loss beyond repair is a liveness/availability
failure, not proof of miner fraud. The profile MUST NOT release a private
opening merely because a challenge was selected; the opening is released to
the assigned checker set under authenticated encryption. Applications needing
stronger privacy MUST use a separate confidential-computing profile.

## 8. Security invariants and explicit non-goals

The following invariants MUST hold:

1. Every settled turn has a TOPLOC commitment and an agent-countersigned,
   monotonic receipt (R3.1); no TOPLOC-less lane exists.
2. Every accepted record binds `task_hash`, `G_n`, `model_hash`, and
   `output_hash` (R3.5), and each task is credited at most once (R3.6).
3. Challenge randomness follows commitment; an assignment excludes the miner;
   and no single miner-controlled trust domain can produce the sole verdict.
4. A settled public credit is either final after an available challenge window
   or explicitly provisional/withheld; evidence absence never means success.
5. A penalty is collectible against aggregate concurrent exposure, and a
   challenge outcome is reproducible from finalized on-chain data plus DA.
6. No timeout releases funds from an unfinalized head, and no protocol verdict
   addresses answer quality.

Non-goals are proving the forward pass in ZK, proving physical FLOPs or energy,
guaranteeing model quality or semantic correctness, hiding data from all
checkers, tolerating a malicious validator quorum, establishing a Nash
equilibrium, or claiming independent error probabilities by multiplying them.
The SOFT tier does not inherit HARD-tier TEE guarantees.

## 9. Open governance and implementation questions

Before production ratification, governance MUST settle: the calibration
admission test and cell invalidation policy; SOFT value caps and pricing
disclosure; the spot-check rate and high-value forcing rule; block-to-time
conversion; checker eligibility and hardware-fingerprint privacy; collateral
reservation across all channels; the slash waterfall and late-fraud recovery;
DA replication/repair and encryption-key custody; accepted-band empirical
calibration; and whether provisional work can enter rewards before finality.
These are not implementation details: changing them changes the security
claim. The profile MUST publish adversarial test results and a conformance
fixture before deleting its NON-AUTHORITATIVE label.

## 10. Traceability to the yellowpaper

| Source requirement/open item | Profile treatment | Status |
| --- | --- | --- |
| R3.1; §3.4/R3.4a | Per-turn TOPLOC commitment, DA reference, post-commit challenge, fail-closed missing evidence | Proposed bridge; E.43 remains open |
| R3.2; E.33 | Admits a calibrated non-TEE miner with session-key receipts, explicit caps and pricing | Concrete proposal; does not amend upstream |
| R3.3; §3.5/R3.5a–c | Three independent checkers, aggregate collateral, standing agent/validator challengers, DA-outside-host | Proposed mechanism; E.45 economics unresolved |
| R3.4 and §3.6 | Validator quorum finalizes checker verdicts; no claim that cooperative receipt alone proves execution | Uses session/dispute interpretation; test required |
| R3.5–R3.6; §12.1(b) | Bound fields, Merkle receipt, monotonic indices, `ProcessedTasks`, no replay | Directly follows requirement; implementation fixture needed |
| §12.1(d), (f), (g), (h) | Reserved escrow, fraud-only disputes, finality-safe clocks, bounded session exposure | Profile choice where SOFT behavior was unspecified |
| E.43 — end-to-end verification/error bridge | Defines commitment, randomness, opening, bands, checker verdicts, and error handling | Candidate closure text, not closure |
| E.44 — cooperative work-credit eligibility | Pays escrow provisionally but delays final public credit and specifies late-fraud recovery | Candidate policy; governance decision required |
| E.45 — effective-challenge incentive model | Makes `p_effective` observable through selection, DA, inclusion, adjudication, and collection; reserves aggregate exposure | Candidate mechanism; no equilibrium claim |
| E.47 — DA availability/anti-grinding | Finalized post-commit randomness, replicated DA, repair/refund semantics | Partial proposal; retention and repair benchmarks open |

Reviewers should compare each row against the cited v0.5.0 sections and the
upstream issue/decision history. Adoption requires an upstream decision; this
file is deliberately only a reviewable research profile.