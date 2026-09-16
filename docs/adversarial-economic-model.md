# Adversarial economic model

This note is the economics companion to the SOFT verification reference. It is
deliberately a model, not a claim that the model has been ratified by FLOP.
The version reviewed here is the published Yellow Paper 0.5.0 (draft). In
particular, E.45 is still `[TBD]` and E.33 is still `[TBD]`; neither supplies
the missing payoff, reservation, or SOFT settlement parameters.

Primary source: [Yellow Paper 0.5.0 draft](https://github.com/flop-labs/yellowpaper/blob/main/yellowpaper.md),
especially §§3.5, 4.2, 12.1–12.3, Appendix A, and Appendix E.

## Scope and status of inputs

The following are **published values or requirements** in the 0.5.0 draft:

* R3.3 requires independent re-execution in another trust domain, collectible
  collateral, and aggregate exposure satisfying the E.45 condition. The
  independent-re-execution mechanics are described more fully in §3.5.
* The spot-check parameter
  `soft_tier_spot_check_rate_ppm = 25_000` (2.5%) is published in Appendix A.
  Its description says that it is SOFT channel spot-check exposure surfaced
  with the calibration snapshot for quality-audit pricing. It is **not** a
  published end-to-end probability of a successful fraud slash.
* `channel_challenger_bond = 100 FLOP` is published in Appendix A and §12.1 as
  the bond posted to open a dispute, for anti-griefing. It is a challenger
  bond, not a stated miner penalty or challenger reward.
* R3.5a requires at least one honest standing challenger: the session agent for
  its own channel or an active validator for any channel. R3.5d specifies a
  floor of three distinct bonded checkers for a sampled or challenged turn, but
  E.53 says that this checker lane is still planned.
* R12.1f gives a seven-day challenge window and defaults miner non-response to
  fraud. The published miner unbonding period is also seven days. This
  alignment is useful, but by itself does not prove that every slashable asset
  remains locked through finality and adjudication.
* R12.2 enforces an in-flight **per-identity reservation slot** cap at
  `open_channel`/`force_open`. It does not yet specify a miner-wide
  reservation measured in collectible FLOP exposure. E.22 and E.45 leave that
  work open.
* E.33 says SOFT has no TEE/SKU evidence, requires an end-to-end entry,
  settlement, dispute, and pricing design, and excludes per-miner demand-floor
  payments because an identity without hardware binding is Sybil-farmable.

Everything else below is a **proposed assumption, variable, or testable
recommendation**, unless marked otherwise. In particular, no value below
silently turns 2.5% into `p_effective`, turns 100 FLOP into
`collectible_penalty`, or treats a reservation slot as collateral.

The public issues motivating this note are [#49][i49] (E.45 lacks a
miner-wide reservation and collectible-penalty formula) and [#50][i50]
(SOFT demand-floor eligibility lacks the hardware-bound Sybil cost of HARD).
The seeded failure evidence requested by [#62][i62] is reported in
[fault-injection-results.md](fault-injection-results.md).

[i49]: https://github.com/flop-labs/yellowpaper/issues/49
[i50]: https://github.com/flop-labs/yellowpaper/issues/50
[i62]: https://github.com/flop-labs/yellowpaper/issues/62

## 1. Players, actions, and payoffs

Use a finalized exposure horizon \(H\), normally the longest time during which
an output can still be challenged, adjudicated, and slashed. Let \(I\) be the
set of a miner's concurrently open channels during \(H\).

* **Miner \(M\)** chooses honest execution or an attack \(a\). An attack can
  omit work, inflate `G_n`, substitute an unbound model/decode path, forge a
  receipt, withhold evidence, or collude with a payer. For an attack set
  \(S\subseteq I\), let \(G(S)\geq0\) be the **gross** benefit before costs:
  avoided honest compute cost plus excess payment or other transfer. Let
  \(K_M(a,S)\) be the attack's operating cost and \(L_M(a,S)\) be the value
  lost through protocol penalties outside the collectible slash (for example,
  a measured future-business loss). Define the single, net exposure variable
  \[
      X(S)=\max\{G(S)-K_M(a,S)-L_M(a,S),\,0\}.
  \]
  This is the proposed operational meaning of
  `total_profitable_exposure`. It is not necessarily the channel escrow or the
  gross request value. \(K_M\) and \(L_M\) are subtracted here once and are
  not subtracted again in the deterrence inequality below.
* **Agent \(A_i\)** buys service and signs receipts. It may challenge its own
  channel when the expected refund, avoided overpayment, or security value
  exceeds its challenge cost. A colluding payer and miner can rationally
  suppress this route.
* **Standing challengers \(K\)** include active validators for any channel and,
  for its own channel, the agent. A challenger pays compute, data retrieval,
  transaction, latency, and capital costs. A challenger can also be censored,
  bribed, or unable to obtain the transcript.
* **Checkers \(J\)** independently re-execute. Their bond, assignment payment,
  and false-verdict penalties are not completely specified: E.53 is a planned
  item. A checker coalition can therefore alter both detection and
  adjudication.
* **DA, inclusion, and finality actors** determine whether evidence can be
  retrieved, a challenge can enter the chain, and its verdict becomes final.
  These are not passive probabilities when a miner, payer, validator, or
  coalition controls them.
* **Other identities and demand agents** can be used for Sybil registration,
  wash demand, reservation griefing, or collusive price discovery. HARD has an
  attested hardware identity; SOFT does not yet have an equivalent binding.

For a risk-neutral miner, normalize the honest payoff to zero and write the
attack payoff as
\[
 U_M(a,S)=X(S)-B_M(a,S),
 \]
where \(B_M\) is the random slash, clawback, or forfeited collateral.
Deterrence means
\[
 \mathbb E[U_M(a,S)]<0
 \quad\Longleftrightarrow\quad
 \mathbb E[B_M] > X(S).
\]
 This is an incentive condition for a specified attack and horizon, not a
 safety proof or a unique equilibrium.

## 2. The effective-challenge probability

The Yellow Paper defines the following chain in §3.5:
\[
\begin{split}
p_{\rm effective}(S)=&
P({\rm selected})\\
&\cdot P({\rm data}\mid{\rm selected})\\
&\cdot P({\rm challenge}\mid{\rm selected,data})\\
&\cdot P({\rm included}\mid{\rm selected,data,challenge})\\
&\cdot P({\rm upheld}\mid{\rm selected,data,challenge,included})\\
&\cdot P({\rm collectible}\mid{\rm selected,data,challenge,included,upheld}).
\end{split}
\]
These are conditional probabilities, not an independence or Markov
assumption. For several channels, use either an attack-level event
\(D_S\) (“at least one economically sufficient fraud outcome is detected and
collected”) or a channel vector \(D_i\). Do not multiply one-channel
probabilities as if channels were independent when they share DA, a
validator set, a miner bond, or a censorship event.

### What each factor must mean

1. **Selection.** For the SOFT tier, 25,000 ppm is the published exposure
   parameter. It may be used as \(P({\rm selected})=0.025\) only as a
   clearly labeled calibration hypothesis. The text does not establish that
   every selected item is fraud-detecting.
2. **Data.** The transcript and the committed turn must be available outside
   the miner's host. A retention window is not the same as successful retrieval
   under withholding or correlated DA failure.
3. **Challenge.** An honest standing challenger must both exist and choose to
   spend resources. R3.5a establishes existence as a requirement; it does not
   establish \(P({\rm challenge})>0\) under a colluding payer or an
   unprofitable validator action.
4. **Inclusion.** The transaction must enter the chain before the challenge
   deadline and survive finality. Congestion, censorship, ordering, and a
   finality stall belong here.
5. **Upheld.** The checker assignment, evidence, quorum, and dispute path must
   distinguish fraud from an honest divergence. A proposed checker reward or
   penalty cannot be counted until it is enforceable.
6. **Collectible.** The miner must still have slashable, non-encumbered
   collateral after all earlier claims, the dispute window, finality, and any
   slash waterfall. A nominal stake balance is not collectible collateral.

The conservative input for a deployed model is a lower confidence bound
\(\underline p_j\) for each conditional factor, obtained separately by
attack class and traffic regime. If a factor is controlled by a rational
party and has no independent incentive, its adversarial lower bound is zero.
Thus a product with an impressive nominal 2.5% is not a deterrence result if
challenge or collection can be suppressed.

The reference fault-injection harness operationalizes this input per attack
class. It records sequential conditional denominators, calculates simultaneous
one-sided factor bounds, and also bounds the complete attack path directly. The
economic helpers receive the smaller result. Consequently, a shared outage or
coalition is retained in each trial's joint outcome and is never replaced by an
independence product of marginal rates.

## 3. Collectible penalty and miner-wide reservation

Use \([z]_+=\max(z,0)\). Let \(C_M^{\rm raw}(t)\) be the miner's collateral
balance before this attack's reservation is applied. Let
\(C_{\rm nonlawful}(t)\) be the portion that cannot lawfully be collected for
this verdict (for example, an excluded account class), and let
\(C_{\rm other\ encumbered}(t)\) be the **single, disjoint union** of prior
claims and reservations that are unavailable to this verdict. These terms
must be mutually disjoint and defined on the same balance basis; neither may
already have been subtracted from \(C_M^{\rm raw}\). Define
\[
\begin{aligned}
 C_{\rm unavailable}(t)
   &= [C_{\rm nonlawful}(t)]_+
      +[C_{\rm other\ encumbered}(t)]_+,\\
 C_{\rm available}(t)
   &=\left[[C_M^{\rm raw}(t)]_+-C_{\rm unavailable}(t)\right]_+,\\
 C_{\rm lawful}(S,t)
   &= [C_{\rm lawful\ cap}(S,t)]_+,\\
 B_{\rm col}(S,t)
   &=\min\!\left(C_{\rm available}(t),C_{\rm lawful}(S,t)\right)
    =\left[\min\!\left(C_{\rm available}(t),C_{\rm lawful}(S,t)\right)\right]_+
    \geq0.
\end{aligned}
\]
Here \(C_{\rm lawful\ cap}(S,t)\) is the maximum amount this specific fraud
verdict can lawfully claw back after its slash cap and waterfall, expressed
as one non-overlapping **legal/path cap** rather than
\(C_{\rm claim}+C_{\rm slashable\ for\ S}\). The protocol must define that
cap; E.45 does not. It must not net \(C_{\rm nonlawful}\) or
\(C_{\rm other\ encumbered}\) a second time. A challenger bond, refundable
agent escrow, and stake reserved for another channel therefore cannot be
counted in either term.
If multiple losses can be proved, the implementation must specify whether
they are one aggregate slash, separate channel slashes, or a first-claim-wins
race. This basis subtracts other encumbrances exactly once and makes the
collectible penalty explicitly nonnegative.

For concurrent channels define a proposed reservation by the deterrence
condition, not by a collateral-to-exposure ratio alone. Let
\(\widehat X_a(S,H)\) be an upper bound on the **net** exposure \(X(S)\) for
attack class \(a\), and let \(\underline p_{\rm effective,a}(S,H)\) be the measured
lower-bound attack-level probability for that class. For a strict margin
\(\delta>0\), let \(R_{\rm dispute}(t)\geq0\) be the nonnegative dispute
capacity reserve; the required collectible reserve is
\[
 B_{\rm req}(a,S,H)
   =\frac{(1+\delta)\widehat X_a(S,H)}
          {\underline p_{\rm effective,a}(S,H)}.
\]
This derives the probability reserve multiplier
\(m_p=(1+\delta)/\underline p_{\rm effective,a}\); it is 40 times \(1+\delta\)
when the only measured factor is 2.5%. If
\(\underline p_{\rm effective,a}=0\), the required reserve is
infinite and the attack class must fail closed or use another proof path. The
admission rule must enforce both:
\[
\begin{split}
 B_{\rm col}^{\rm lower}(a,S,t)&\ \geq B_{\rm req}(a,S,H),\\
  C_{\rm available}(t)
    &\ \geq B_{\rm req}(a,S,H)+R_{\rm dispute}(t),
\end{split}
\]
which explicitly implies the measured lower-bound test
\[
 \underline p_{\rm effective,a}(S,H)\,B_{\rm col}^{\rm lower}(a,S,t)
   \ >\ \widehat X_a(S,H)
\]
when the declared strict margin is positive. The rule is evaluated for every
feasible concurrent attack set \(S\) and attack class \(a\), at every
`open_channel`, `force_open`, and `top_up`. Here
\(B_{\rm col}^{\rm lower}\) must be computed from the non-overlapping
\(C_{\rm available}\) and \(C_{\rm lawful}\) terms above, including slash
caps, existing claims, unlocked funds, and the slash waterfall exactly once.
The check is atomic and
rejects an operation when either inequality fails. Equivalently, an
implementation may reserve the maximum \(B_{\rm req}\) over all feasible
\((a,S)\), but it may not use one per-job check as a proxy for the maximum.
Settlement, expiry, and a finalized fraud verdict release only the
corresponding reservation.

This is distinct from the current R12.2 count of in-flight slots. Four slots
can contain four tiny channels or four channels whose aggregate attack
exposure exceeds one bond. Conversely, R7.1c correctly says that empirical
host capacity must not be multiplied by GPU count, channel count, session
count, or batch size. A capacity estimate and an economic slash reserve are
different quantities and must not be conflated.

For a single shared slash event, the attack-level deterrence test is
\[
 \underline p_{\rm effective}(S)\,
 B_{\rm col}(S)
 >
 X(S).
\]
 If no cross-channel aggregate verdict is possible, a safer test is the
 exact expected loss
\[
 \mathbb E[B_M(S)] =
 \sum_{i\in S}P(D_i)\,B_i
 -\text{overlap correction},
\]
 where the overlap correction prevents counting one shared balance multiple
 times. A per-job test cannot replace the attack-level test.

### Concurrent-exposure example

Suppose, only for illustration, that each of four simultaneous channels has
net exposure \(X_i=1\) FLOP after its attack costs and non-slash losses, so
the aggregate net exposure is \(X(S)=4\) FLOP. The miner has one shared,
hypothetical 100 FLOP **miner collectible penalty** (not the published
100 FLOP challenger bond). There are two different selection models:

* **Perfectly correlated selection:** one draw selects all four channels or
  none. If all other chain factors equal one and the 2.5% spot-check is
  treated as selection, \(p_S=0.025\), so the expected shared loss is
\[
  0.025\cdot100=2.5\ {\rm FLOP}.
\]
  The required penalty from \(p_SB_{\rm col}>X\) is
  \(B_{\rm col}>4/0.025=160\) FLOP, before any strict safety margin. Thus
  100 FLOP fails even though a mistaken per-channel comparison would say
  \(2.5>1\).
* **Independent per-channel selection:** each channel is selected with
  probability 0.025, and one shared slash occurs if at least one selection
  detects the attack. Then
  \[
    p_S=1-(1-0.025)^4=0.096312\quad\text{and}\quad
    p_SB_{\rm col}=9.6312\ {\rm FLOP}
  \]
  for the 100 FLOP bond. The corresponding shared-penalty threshold is
  \(B_{\rm col}>4/0.096312\approx41.53\) FLOP. This is not four independent
  100 FLOP penalties; it is one shared penalty conditioned on at least one
  selected channel.

The published spot-check description does not establish either correlation
model or any end-to-end slash probability. A reservation must therefore use
the measured lower bound for the actual attack-level event. Under the
correlated model, the probability-derived reserve multiplier is
\(1/0.025=40\) before margin; under the independent model for these four
channels it is \(1/0.096312\approx10.38\). The admission rule above, rather
than a fixed collateral-to-\(\sum_iX_i\) ratio, is the proposed E.45 fix.

## 4. Challenger expected utility

The 100 FLOP `channel_challenger_bond` is a published anti-griefing input.
Let \(b_c=100\) FLOP in a baseline illustration. It must not be substituted
for \(B_{\rm col}\). A challenger may have the following proposed payoff
parameters:

* \(r_c\): protocol-paid reward if the challenge is upheld;
* \(v_A\): agent's avoided overpayment/refund/security value;
* \(f_c\): checker or audit payment, if an assignment is actually made;
* \(c_c\): compute, retrieval, transaction, and opportunity cost;
* \(\ell_c\): loss of the bond when the challenge is rejected, invalid, or
  expires under the eventual rules;
* \(d_c\): expected value lost to delay, lockup, or retaliation.

If \(q_c=P({\rm upheld}\mid{\rm submitted})\), then for a validator:
\[
 EU_K =
 q_c(r_c+f_c)
 -(1-q_c)\ell_c b_c
 -c_c-d_c.
\]
 For the session agent, replace or augment \(r_c+f_c\) by \(v_A\). Return of
the bond on an upheld challenge is omitted from the expression because it is
principal recovery, not a reward. If the final design burns the bond on a
different class of failure, that term must be made explicit.

The proposed incentive-compatibility requirement is
\[
 \underline{EU}_K({\rm challenge}\mid{\rm real\ fraud})\geq0,
\qquad
 EU_K({\rm frivolous\ challenge})<0.
\]
 Both inequalities need testing across validator sizes and congestion. A
standing-challenger requirement without the first inequality merely assumes
that somebody pays. A high bond without a reward can make honest challenges
uneconomic; a low bond with no loss for false challenges invites griefing.
Existing audit-pool or checker payments must not be treated as \(r_c\) unless
their eligibility and amount cover this action.

## 5. Worked baseline and sensitivity

The baseline below intentionally separates published facts from proposed
simplifications:

* **Published:** \(q_{\rm spot}=25{,}000/1{,}000{,}000=0.025\) and
  \(b_c=100\) FLOP.
* **Illustrative assumptions, not published:** treat the spot rate as
  \(P({\rm selected})\); set all other \(p_{\rm effective}\) factors to one;
  treat 100 FLOP as a hypothetical collectible miner penalty
  \(C_{\rm col}=100\), solely to show arithmetic.

Under those assumptions:
\[
 p_{\rm effective}=0.025,\qquad
 \mathbb E[B_M]=0.025\cdot100=2.5\ {\rm FLOP}.
\]
 Therefore the attack is deterred only when its net profitable exposure is
strictly below 2.5 FLOP (and the miner has no other profitable response).
This conclusion is **not** supported by the published parameters because the
100 FLOP amount is a challenger bond, not a miner slash.

As a second arithmetic check, assume (again, only for sensitivity) conditional
factors after selection of data \(0.98\), challenge \(0.80\), inclusion \(0.99\),
upheld \(0.95\), and collectible \(0.90\). Their product is \(a=0.6636\).
Then \(p_{\rm effective}=0.025a=0.01659\).

| Selection / assumed `C_col` | Post-selection factor \(a\) | Expected collectible loss \(pC_{\rm col}\) | Net exposure \(X\) strictly below this could pass the simplified test |
|---:|---:|---:|---:|
| 0.5% / 100 FLOP | 1.0000 | 0.50 FLOP | 0.50 FLOP |
| 2.5% / 100 FLOP | 1.0000 | 2.50 FLOP | 2.50 FLOP |
| 2.5% / 100 FLOP | 0.6636 | 1.66 FLOP | 1.66 FLOP |
| 2.5% / 1,000 FLOP | 0.6636 | 16.59 FLOP | 16.59 FLOP |
| 5.0% / 1,000 FLOP | 0.6636 | 33.18 FLOP | 33.18 FLOP |
| 10.0% / 10,000 FLOP | 0.6636 | 663.60 FLOP | 663.60 FLOP |

The table is a dimensional sanity check, not a parameter recommendation. In
particular, it assumes a single attack event, a fixed penalty, and no
correlation. A shared censoring event can reduce every row's realized
collection probability; a larger concurrent set can increase the right-hand
side without increasing the left-hand side.

## 6. Sybil and wash-demand attacks

### SOFT supply and demand-floor farming

E.33 explicitly identifies per-miner demand-floor payments as Sybil-farmable
without a hardware identity. Issue #50 gives the concrete attack: one
SOFT-capable host registers \(M\) staked identities, independently passes the
calibration minimum, and claims an identity-priced floor. The marginal
identity costs a stake bond, not a distinct device.

For an operator with \(M\) identities, write the net farming payoff as
\[
 U_{\rm farm}(M)=M F_{\rm floor}
 -C_{\rm stake}(M)-C_{\rm calibration}(M)
 -C_{\rm concurrency}(M)-C_{\rm detection}(M).
\]
 If \(U_{\rm farm}(M)>0\) for any materially large \(M\), the floor is
farmable. The proposed cost function must be based on independently
justified stake and scarce capacity, not merely identity count. Calibration
throughput is not a device-uniqueness proof: R7.1c prevents multiplying one
host's capacity within an identity, but does not cross-link distinct SOFT
identities.

Until an equivalent binding is measured, the conservative choices are:

1. exclude SOFT from per-identity demand floors (the strict reading of E.33);
2. pay only against a stake-bond/capacity unit, with a hard aggregate operator
   cap where an operator can be established; or
3. add and validate a non-TEE device-binding signal before admitting a floor.

Option 2 does not magically make identities unique; it makes splitting
economically linear and must still be tested against borrowed stake and
delegation. Any choice is a proposal until E.33 ratifies it.

### Wash demand and reservation griefing

An agent or coalition can create fake jobs, bids, or channels to make
utilization and scarcity appear high, occupy miner reservations, or harvest
identity-priced rebates. For \(M\) fake identities:
\[
 U_{\rm wash}=V_{\rm price\ manipulation}
 +V_{\rm rebate}
 -M(C_{\rm stake}+C_{\rm reservation}+C_{\rm fees})
 -C_{\rm capital\ lock}
 -C_{\rm detection}.
\]
 A wash-resistant design needs \(U_{\rm wash}<0\) for the cheapest attack, not
just a reputation penalty. R12.3's mechanism-level responses (re-randomize
auctions, coarsen the grid, or inject synthetic demand) are preferable to
punishing inferred intent. Synthetic demand must not be counted as evidence
of honest utilization or as a challenger.

Tests should vary stake splitting, borrowed stake, simultaneous identities,
cancelled channels, and delayed settlement. Count only finalized paid work
with a non-reversible cost when calculating demand floors or capacity
utilization.

## 7. Availability, censorship, and coalitions

The probability chain is adversarial at exactly the points that matter:

* A colluding payer can set \(P({\rm challenge}\mid\cdots)=0\) unless an
  independent validator has both access and positive expected utility.
* A miner can attempt to unbond or transfer assets before the verdict.
  The published seven-day windows are a useful starting constraint, but a
  slash lock must cover the full path through finality, not merely the
  nominal challenge window.
* A miner or validator coalition can withhold DA, censor a challenge, or
  delay finality. If data retrieval or inclusion is not independently
  available, the lower-bound factor is zero for that coalition.
* A checker cartel can make \(P({\rm upheld})\) low. The proposed three-seat
  distinct-fingerprint rule and the \(q^3\) capture intuition are not a
  substitute for a live registry, assignment proof, checker bond, and
  overturned-verdict penalty; E.53 records those gaps.
* Bribery can be cheaper than the penalty. Include the largest credible bribe
  in the miner's \(K_M\) or explicitly model it as a coalition transfer.

A useful availability condition for a claim is therefore:
\[
\underline p_{\rm data}\,
\underline p_{\rm inclusion}\,
\underline p_{\rm finality}\,
\underline p_{\rm collectible}>0
\]
under the stated threat model, and \(EU_K\geq0\) for at least one
independent challenger. If any term is zero under a permitted coalition, the
normal deterrence inequality must not be advertised for that coalition.
Fail-closed settlement or a high-value ZK proof is then the safer response,
not a more optimistic probability estimate.

## 8. Parameter-selection procedure

The following procedure is intended to turn E.45 from a prose inequality into
a falsifiable profile.

1. **Declare attack classes and horizon.** Enumerate omission, inflation,
   substitution, non-delivery, evidence withholding, payer collusion, and
   checker collusion. Set \(H\) to challenge deadline plus finality and
   unbond/slash-lock tail. Publish whether values are per turn, channel, or
   concurrent miner.
2. **Compute exposure before admission.** For each feasible attack class and
   concurrent set publish \(\widehat X_a(S,H)\), the upper bound on aggregate
   net exposure after attack costs and non-slash losses. Include tariff,
   avoided cost, refundable escrow, and plausible bribes in the gross-benefit
   calculation before subtracting those costs once. Measure
   \(\underline p_{\rm effective,a}(S,H)\), then reject opens and top-ups
   unless
   \(B_{\rm col}^{\rm lower}\geq
   (1+\delta)\widehat X_a/\underline p_{\rm effective,a}\)
    **and** \(C_{\rm available}\geq
    (1+\delta)\widehat X_a/\underline p_{\rm effective,a}+R_{\rm dispute}\).
3. **Measure each conditional factor.** Run seeded audits for selection, DA
   retrieval, challenge response, inclusion under congestion, checker verdict,
   and collection after attempted unbond. Report lower confidence bounds by
   tier, attack class, and traffic regime. Never infer a product from marginal
   rates without a conditional-independence argument.
4. **Choose collateral from collection, not balance.** Exclude delegated,
   already-reserved, refundable, or unlocked funds. Define slash ordering,
   aggregate-vs-per-channel claims, and treatment of simultaneous fraud.
5. **Solve challenger incentives.** Select \(r_c\), bond loss, payment timing,
   and evidence cost so that the lower-bound challenger utility is non-negative
   for real fraud and negative for a false challenge. Publish the challenger
   type and any validator audit payment used in the calculation.
6. **Stress Sybil and wash strategies.** Optimize \(U_{\rm farm}(M)\) and
   \(U_{\rm wash}\) over identity count, borrowed stake, common hosts,
   concurrency, cancellations, and collusion. Do not grant SOFT floor
   eligibility until the cheapest positive strategy is removed or bounded.
7. **Set a margin and re-test.** Choose \(\delta\) and a target loss margin
   only after steps 1–6; the probability multiplier is
   \((1+\delta)/\underline p_{\rm effective,a}\), not a free collateral ratio.
   Re-run after
   changes to spot rate, bond, tariff, capacity, finality, or unbonding.
   Parameters are unsafe when any lower confidence bound or collectible
   reserve fails.

## 9. Failure conditions

The model must report “not deterred” or “not established” when any of these
conditions holds:

* a miner can open concurrent exposure with
  \(\underline p_{\rm effective}(S)B_{\rm col}(S)\leq X(S)\), or the
  reservation is checked only per identity, slot, or job;
* the implementation treats the 100 FLOP challenger bond as the miner's
  collectible penalty;
* 2.5% is used as `p_effective` without data, challenge, inclusion, upheld,
  and collection measurements;
* any required factor is controlled by a colluding party with no independent
  incentive and no positive lower bound;
* the slash lock ends before the complete challenge, adjudication, and
  finalized collection path;
* a standing challenger exists in name but \(EU_K<0\), evidence is unavailable,
  or censorship makes timely inclusion unlikely;
* checker assignment, distinctness, bond loss, or overturn handling is not
  enforceable;
* SOFT floor farming or wash demand has positive net payoff at a realistic
  identity count;
* a parameter change increases exposure faster than locked collateral or
  leaves an old reservation in place after top-up/renewal;
* the result relies on risk aversion, reputation, or future business that the
  protocol neither measures nor makes costly.

## 10. Falsifiable recommendations

These are recommendations for the next E.45/E.33 revision, not claims about
the current protocol:

1. **Specify and enforce miner-wide reservations.** Add an atomic
   `open_channel`/`force_open`/`top_up` check for every feasible attack class
   and concurrent set:
   \[
     B_{\rm col}^{\rm lower}\ >
       \widehat X_a(S,H)/\underline p_{\rm effective,a}(S,H)
   \]
   with a declared margin \(\delta\), and require
   \(C_{\rm available}\geq B_{\rm req}+R_{\rm dispute}\). Use per-channel
   reservation identifiers and no double counting. A regression test should
   show that the \(N+1\)th
   channel is rejected when the measured expected slash no longer exceeds
   aggregate net exposure, even when every individual channel passes.
2. **Separate the two bonds in the wire and accounting model.** Keep
   `channel_challenger_bond` as anti-griefing, define `collectible_penalty`
   from actually slashable miner collateral, and publish the slash waterfall.
   The 2.5% × 100 = 2.5 FLOP calculation must fail a conformance test if it is
   presented as the production penalty.
3. **Publish a challenge reward and utility bound.** Define reward,
   reimbursement, false-challenge loss, and timing. Measure
   \(EU_K\) for an agent and an independent validator under congestion; do not
   rely on “honest standing challenger” as an economic assumption.
4. **Make availability a gate.** Before counting a spot check toward
   deterrence, measure external DA retrieval, inclusion, and finality lower
   bounds. If any bound collapses, fail closed or escalate high-value claims
   to the stronger proof path rather than silently accepting.
5. **Resolve SOFT floor eligibility explicitly.** Until cross-identity
   device-binding or an equivalent economic bound is demonstrated, exclude
   per-identity SOFT floors or cap them per independently bonded capacity.
   A reproducible one-host/\(M\)-identity experiment should show
   \(U_{\rm farm}(M)\leq0\) over the published operating range.
6. **Publish an attack-level dashboard.** For each tier show lower-bound
   \(p_{\rm effective}\), \(B_{\rm col}\), \(X_{\max}\), reservation utilization,
   challenger utility, DA/inclusion success, and the largest tested Sybil and
   wash payoff. A parameter is acceptable only if the dashboard and the
   concurrent-opening regression pass with stated confidence.

These recommendations preserve the Yellow Paper's useful conditional
inequality while making clear what it can and cannot establish. They also
directly test the two gaps identified by issues #49 and #50 rather than
assuming that a spot-check percentage, an anti-griefing bond, or a count of
identities is itself an economic security proof.