"""Overall Evaluation Criterion: expected loss per decision (in dollars,
per SPEC.md's cost matrix), the sanctions/confirmed-history disqualifying
gate, policy-clause coverage, and the guardrail checks that stop a report
from overstating confidence.

Kohavi/Tang/Xu (Trustworthy Online Controlled Experiments) names three gaps
this module closes: (1) a single accuracy number is not an OEC, an OEC is a
business-relevant composite chosen upfront; (2) a report must alert on
violated assumptions (thin sample, unstable contract) instead of quietly
returning a number the reader will over-trust; (3) an OEC computed over an
unmeasured slice of the problem is worse than no OEC, because it looks
complete.

Operator ask, 2026-08-19: the metrics must be "a good/great representation
of POLICY.md" plus "a compound mathematical way to composite all." This
module answers both: coverage first (does a case exist for every clause the
policy names), then one dollar-denominated composite.

Correction, same night: an earlier version of this file invented a unitless
0-10 cost matrix with per-clause severity multipliers (1.0x-2.0x), before
re-reading docs/prd/SPEC.md's own KPI table, which already specifies real
dollar costs (FA=$2,000, FH=$45, FR=$600, with a stated rationale for each)
and a hard rule ("Sanctions recall must be 1.0; a single miss is
disqualifying") that predates this session by months. Two competing cost
models in one repo is a defect a reviewer catches on sight; SPEC.md's
figures win because they are the actual spec, not tonight's invention.
The clause tags did not get thrown away: they are the better tool for
coverage (does a case exist per policy section) and for slicing (which
clause do the misses land on), and the sanctions "zero tolerance" line is
now a disqualifying GATE (matching the policy's own word) rather than a
cost multiplier.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

DECISIONS = ("APPROVE", "HOLD", "REJECT")

# POLICY.md's own section structure. Every case in data/labels.json is
# tagged with exactly one of these via `policy_clause`, used for coverage
# and slicing, not for cost weighting (see module docstring).
POLICY_CLAUSES: dict[str, str] = {
    "sanctions_watchlist": "zero tolerance: a genuine sanctions match is disqualifying",
    "account_linkage": "a genuine connection to known fraud... is a serious concern",
    "transaction_activity": "systematic testing... and... a bust-out[] are fraud",
    "identity_ownership": "where the party... cannot presently be established and money is exposed, the risk is unresolved",
    "confirmed_history": "a confirmed, adjudicated problem against the same party is disqualifying",
    "weighing_proportionality": "the response is proportionate to what is at stake",
    "evidence_discipline": "an account holder's own account of events is not evidence on its own",
    "data_quality_flag": "a flag with nothing substantiating it... is a data-quality question, not a confirmed problem",
}

# Clauses where the POLICY's OWN word is "zero tolerance" / "disqualifying",
# and SPEC.md independently states the matching KPI ("Sanctions recall must
# be 1.0; a single miss is disqualifying"). A miss on either is not a cost,
# it is a gate: the cell fails eligibility outright, regardless of its EL.
DISQUALIFYING_CLAUSES = frozenset({"sanctions_watchlist", "confirmed_history"})

# SPEC.md's KPI table, verbatim: "Expected loss per 1k cases: sum(cost[error_type]
# x rate) using an explicit cost matrix. Cost matrix: FA=$2,000 (realized fraud
# loss, avg of case exposures), FH=$45 (support touch + churn risk), FR=$600
# (lost LTV)." This matrix MUST match engine/export.py's error_cost() exactly:
# export.py is the pre-existing, UI-connected implementation (feeds
# ui/public/benchmark.json, which is what PRODUCT.md's matrix tiles render),
# and notebooks/analysis.ipynb's cell 4 has its own copy of the same formula.
# An earlier version of this file (same night) invented a DIFFERENT six-cell
# mapping without checking export.py first, a real defect caught only when
# the operator asked whether the notebook was presentation-ready and a full
# read of it surfaced the mismatch. Fixed by matching export.py's four
# off-diagonal branches instead of re-deriving new assumptions:
#   REJECT->APPROVE = FA ($2,000)      REJECT->HOLD    = FA*0.25 ($500)
#   APPROVE->REJECT = FR ($600)        APPROVE->HOLD   = FH ($45)
#   HOLD->REJECT    = FR ($600)        HOLD->APPROVE   = FH ($45)
# If this ever needs to change again, change export.py's error_cost() FIRST
# (it is the one already wired to what a reviewer sees) and port the same
# four branches here, not the other way around.
# Grounding check (2026-08-23): mean at_risk_usd over the 4 cases actually
# labeled expected=REJECT (the only cases where FA fires) is $4,251.63
# (CASE-101-P1B $0, CASE-102 $6.50, CASE-106 $8,000, CASE-107 $9,000) --
# roughly 2x the stated $2,000, but n=4 with one $0 case is itself too
# thin to treat as ground truth over the stated figure. Read as: $2,000 is
# not contradicted by the suite's own data, and the suite is too small to
# settle the question either way. --sweep covers $1k-$5k, which brackets
# this computed mean on both sides.
FA_USD = 2000.0   # false approve: realized fraud loss (expected REJECT, decided APPROVE)
FH_USD = 45.0     # false hold: support touch + churn risk
FR_USD = 600.0    # false reject: lost LTV

COST_MATRIX_USD: dict[str, dict[str, float]] = {
    "APPROVE": {"APPROVE": 0.0, "HOLD": FH_USD, "REJECT": FR_USD},
    "HOLD":    {"APPROVE": FH_USD, "HOLD": 0.0, "REJECT": FR_USD},
    "REJECT":  {"APPROVE": FA_USD, "HOLD": FA_USD * 0.25, "REJECT": 0.0},
}

# Guardrail floors: a cell below these is flagged, not silently scored.
MIN_N_FOR_TRUST = 8          # Kohavi: below this, a CI is too wide to rank on
MIN_CONTRACT_RATE = 0.5      # half or more unparseable output invalidates acc
MAX_CI_WIDTH = 0.5           # Wilson hi-lo above this: don't rank on it

# The decision suite: the kinds whose cases feed accuracy and expected loss.
# Injection and metamorphic cases carry expected labels too, but they measure
# robustness (resistance, invariance), and blending them into acc/EL is the
# tier-blending anti-pattern SPEC.md's "Label tiers" section forbids. Added
# 2026-08-24 with the injection/metamorphic/coverage sets; cells run before
# that date contain only decision-suite cases, so their numbers are unchanged.
DECISION_SUITE_KINDS = ("golden", "perturbation")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Lives here (not runner.py) since 2026-08-24 so
    the export can compute cell trust with the exact same bounds the report
    uses; one implementation, two consumers."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - m), min(1.0, c + m))


MAX_FLIP = 0.25  # above this, repeated cases disagree; the cell is unrankable


def cell_trust(con: sqlite3.Connection, prompt_version: str, model_id: str,
               wilson_lo: float | None, wilson_hi: float | None,
               mean_flip: float | None) -> tuple[str, list[str], OECResult]:
    """One verdict per cell, shared by report and export: 'ok' | 'FLAG' |
    'DISQ', the violation strings, and the OECResult behind them. One
    implementation so the terminal report and the UI can never disagree
    about which cells are rankable."""
    oec = expected_loss(con, prompt_version, model_id)
    violations = list(oec.violations)
    if wilson_lo is not None and wilson_hi is not None:
        violations += guardrail_check(con, prompt_version, model_id, wilson_lo, wilson_hi)
    if mean_flip is not None and mean_flip > MAX_FLIP:
        violations.append(
            f"flip {mean_flip:.2f} > {MAX_FLIP} across repeated cases "
            "(decisions disagree across repeats; accuracy shown is the "
            "first run's luck, do not rank on this cell)")
    trust = "DISQ" if oec.disqualified else ("ok" if not violations else "FLAG")
    return trust, violations, oec


@dataclass
class ClauseCoverage:
    clause: str
    policy_cite: str
    n_cases: int
    case_ids: list[str] = field(default_factory=list)


def coverage_report(con: sqlite3.Connection) -> list[ClauseCoverage]:
    """Does a case exist for every clause the policy names? A composite
    metric over an unmeasured clause is a hole wearing a number; naming the
    hole is the point (advisor, 2026-08-19: 'the coverage half is a matrix
    of policy clause x does-a-case-exist... nearly free... costs one
    table')."""
    rows = con.execute(
        "SELECT policy_clause, case_id FROM cases WHERE retired=0"
    ).fetchall()
    by_clause: dict[str, list[str]] = {c: [] for c in POLICY_CLAUSES}
    untagged: list[str] = []
    for clause, case_id in rows:
        if clause in by_clause:
            by_clause[clause].append(case_id)
        else:
            untagged.append(case_id)
    out = [
        ClauseCoverage(clause=c, policy_cite=POLICY_CLAUSES[c],
                        n_cases=len(ids), case_ids=sorted(ids))
        for c, ids in by_clause.items()
    ]
    if untagged:
        out.append(ClauseCoverage(clause="UNTAGGED", policy_cite="(no policy_clause set)",
                                   n_cases=len(untagged), case_ids=sorted(untagged)))
    return out


@dataclass
class OECResult:
    prompt_version: str
    model_id: str
    n: int
    expected_loss_usd_per_1k: float | None
    disqualified: bool                 # True: a sanctions/confirmed-history miss occurred
    disqualified_cases: list[str] = field(default_factory=list)
    trustworthy: bool = True
    violations: list[str] = field(default_factory=list)


def expected_loss(
    con: sqlite3.Connection,
    prompt_version: str,
    model_id: str,
    cost_matrix: dict[str, dict[str, float]] = COST_MATRIX_USD,
    fa_usd: float | None = None,
) -> OECResult:
    """First-run-per-case decisions only (repeats feed flip rate, not the
    OEC), joined against the case's expected label AND policy_clause.
    Ungraded cases (expected IS NULL) are excluded, not treated as free.
    `fa_usd` overrides FA_USD for the sensitivity sweep (SPEC.md: 'stated
    as assumptions, sensitivity-analyzed'); the other five cells stay put,
    isolating the question that's actually arguable, the $2,000 figure."""
    matrix = cost_matrix
    if fa_usd is not None:
        # Mirror export.py's error_cost() shape: only the two REJECT-expected
        # cells derive from FA (APPROVE=FA, HOLD=FA*0.25); HOLD->APPROVE is
        # pinned to FH regardless of FA, matching export.py exactly.
        matrix = {
            "APPROVE": dict(cost_matrix["APPROVE"]),
            "HOLD": dict(cost_matrix["HOLD"]),
            "REJECT": {**cost_matrix["REJECT"], "APPROVE": fa_usd, "HOLD": fa_usd * 0.25},
        }

    rows = con.execute(
        "SELECT r.case_id, r.decision, r.contract_ok, r.repeat_idx, "
        "c.expected, c.policy_clause "
        "FROM runs r JOIN cases c USING(case_id) "
        "WHERE r.prompt_version=? AND r.model_id=? AND c.expected IS NOT NULL "
        f"AND c.kind IN {DECISION_SUITE_KINDS!r} "
        # protocol-temperature rows only: high-temp self-consistency samples
        # are their own analysis, never the accuracy/EL substrate
        "AND (r.temperature IS NULL OR r.temperature <= 0.21) "
        "ORDER BY r.repeat_idx",
        (prompt_version, model_id),
    ).fetchall()

    first: dict[str, tuple[str | None, int, str, str | None]] = {}
    for case_id, decision, contract_ok, repeat_idx, expected, clause in rows:
        if case_id not in first:
            first[case_id] = (decision, contract_ok, expected, clause)

    n = len(first)
    violations: list[str] = []

    if n == 0:
        return OECResult(prompt_version, model_id, 0, None,
                          disqualified=False, trustworthy=False,
                          violations=["no graded runs"])

    contract_rate = sum(c for _, c, _, _ in first.values()) / n
    if contract_rate < MIN_CONTRACT_RATE:
        violations.append(
            f"contract_rate {contract_rate:.2f} < {MIN_CONTRACT_RATE} "
            "(over half the output was unparseable; loss below is computed "
            "only over the parseable subset, so it is optimistic)")
    if n < MIN_N_FOR_TRUST:
        violations.append(f"n={n} < {MIN_N_FOR_TRUST} (too thin to rank on)")

    total_loss = 0.0
    graded = 0
    unparseable = 0
    disqualified_cases: list[str] = []
    for case_id, (decision, _contract_ok, expected, clause) in first.items():
        # SPEC.md: "Sanctions recall must be 1.0; a single miss is
        # disqualifying." POLICY.md: "zero tolerance." A miss on either
        # disqualifying clause is a gate failure, not a cost: it does not
        # get averaged away by 11 other correct cases.
        if clause in DISQUALIFYING_CLAUSES and decision != expected:
            disqualified_cases.append(case_id)

        if decision not in DECISIONS:
            # No recoverable decision: a real, separate failure mode from a
            # wrong-but-parseable decision (contract_ok already flags it as
            # a guardrail). Charge the worst cost reachable FROM THIS
            # EXPECTED LABEL (never a different label's worst cell, the bug
            # this file already fixed once tonight): still costs more than
            # any parseable miss, never becomes an off-scale outlier.
            total_loss += max(matrix[expected].values())
            unparseable += 1
            graded += 1
            if clause in DISQUALIFYING_CLAUSES:
                disqualified_cases.append(case_id)
            continue
        total_loss += matrix[expected][decision]
        graded += 1

    if unparseable:
        violations.append(
            f"{unparseable}/{n} case(s) had no recoverable decision "
            "(charged worst-comparable cost, not free; see contract_ok "
            "guardrail for the underlying failure)")

    disqualified = len(disqualified_cases) > 0
    if disqualified:
        violations.append(
            f"DISQUALIFIED: miss on {sorted(set(disqualified_cases))} "
            "(sanctions or confirmed-history clause; SPEC.md: 'a single "
            "miss is disqualifying', zero tolerance, not averaged into EL)")

    el_per_1k = (total_loss / graded) * 1000 if graded else None

    return OECResult(
        prompt_version=prompt_version,
        model_id=model_id,
        n=n,
        expected_loss_usd_per_1k=el_per_1k,
        disqualified=disqualified,
        disqualified_cases=sorted(set(disqualified_cases)),
        trustworthy=(len(violations) == 0),
        violations=violations,
    )


def sensitivity_sweep(
    con: sqlite3.Connection,
    prompt_versions: list[str],
    model_id: str,
    fa_values: tuple[float, ...] = (1000.0, 1500.0, 2000.0, 3000.0, 5000.0),
) -> dict[float, list[tuple[str, float | None]]]:
    """Does the version ranking hold if FA (SPEC.md's most arguable figure,
    'realized fraud loss, avg of case exposures') moves? SPEC.md commits to
    running this in the notebook; this is the same test from the engine
    side, over the real banked runs. Only FA moves; FH/FR/the HOLD-cell
    assumptions stay fixed, isolating the one number most likely disputed."""
    out: dict[float, list[tuple[str, float | None]]] = {}
    for fa in fa_values:
        ranked = sorted(
            ((pv, expected_loss(con, pv, model_id, fa_usd=fa).expected_loss_usd_per_1k)
             for pv in prompt_versions),
            key=lambda t: (t[1] is None, t[1]),
        )
        out[fa] = ranked
    return out


def guardrail_check(con: sqlite3.Connection, prompt_version: str, model_id: str,
                     wilson_lo: float, wilson_hi: float) -> list[str]:
    """Assumption checks beyond the OEC itself: CI width, and a
    false-guardrail metric (did this prompt/model ever REJECT a case whose
    expected label was APPROVE? That is the collateral-damage guardrail
    Kohavi warns an OEC alone can hide)."""
    violations: list[str] = []
    if (wilson_hi - wilson_lo) > MAX_CI_WIDTH:
        violations.append(
            f"CI width {wilson_hi - wilson_lo:.2f} > {MAX_CI_WIDTH} "
            "(too wide to claim this cell beats another)")

    false_rejects = con.execute(
        "SELECT COUNT(*) FROM runs r JOIN cases c USING(case_id) "
        "WHERE r.prompt_version=? AND r.model_id=? "
        "AND c.expected='APPROVE' AND r.decision='REJECT' "
        f"AND c.kind IN {DECISION_SUITE_KINDS!r}",
        (prompt_version, model_id),
    ).fetchone()[0]
    if false_rejects:
        violations.append(
            f"{false_rejects} case(s) with expected APPROVE decided REJECT "
            "(guardrail: a high-accuracy prompt can still burn good accounts)")

    return violations


def sprt(outcomes: list[int], p0: float = 0.75, p1: float = 0.92,
         alpha: float = 0.05, beta: float = 0.10) -> tuple[str, float, int]:
    """Wald's sequential probability ratio test over a challenger's per-case
    correctness stream (fixed case order, first run per case). H0: the
    challenger's true rate is at most p0; H1: at least p1. Returns
    (verdict, log_lr, n_consumed) where verdict is 'accept' (H1, promote),
    'reject' (H0, stop wasting runs), or 'continue' (evidence exhausted
    before either boundary: the fixed-N Wilson interval remains the answer).

    Why it exists (2026-08-24, operator's PPDAC brief): a fixed-N benchmark
    burns the full suite on a challenger that is clearly losing by case 5.
    SPRT is the classical stopping rule for that; defaults set the
    indifference region around the observed champion rate (0.92 on the
    12-case suite) with a floor a losing rung would sit under. It never
    replaces the trust gates: a promoted challenger still needs contract,
    flip, and zero-tolerance gates green before it ranks.
    """
    import math
    if not (0 < p0 < p1 < 1):
        raise ValueError("need 0 < p0 < p1 < 1")
    up = math.log((1 - beta) / alpha)        # accept H1 at or above
    down = math.log(beta / (1 - alpha))      # accept H0 at or below
    llr = 0.0
    for i, ok in enumerate(outcomes, start=1):
        llr += math.log(p1 / p0) if ok else math.log((1 - p1) / (1 - p0))
        if llr >= up:
            return "accept", llr, i
        if llr <= down:
            return "reject", llr, i
    return "continue", llr, len(outcomes)
