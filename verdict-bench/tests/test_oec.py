"""Boundary tests for engine/oec.py: dollar expected loss (SPEC.md's own
cost matrix), the sanctions/confirmed-history disqualifying gate, policy-
clause coverage, and guardrail checks. Real in-memory SQLite, no mocks,
per the no-mocks standing rule."""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
from oec import (  # noqa: E402
    expected_loss, guardrail_check, coverage_report, sensitivity_sweep,
    COST_MATRIX_USD, FA_USD, FH_USD, FR_USD, POLICY_CLAUSES,
    DISQUALIFYING_CLAUSES, MIN_N_FOR_TRUST,
)

SCHEMA = (ROOT / "engine" / "schema.sql").read_text()


def seed_db(rows: list[tuple], cases: list[tuple]) -> sqlite3.Connection:
    """cases: (case_id, expected) or (case_id, expected, clause)."""
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    con.execute("INSERT INTO prompts VALUES ('v1', 'x', 'hyp')")
    for case in cases:
        case_id, expected = case[0], case[1]
        clause = case[2] if len(case) > 2 else None
        con.execute(
            "INSERT INTO cases (case_id,kind,expected,label_source,path,policy_clause) "
            "VALUES (?,?,?,?,?,?)", (case_id, "golden", expected, "expert", "x", clause))
    for i, (case_id, decision, contract_ok, repeat_idx) in enumerate(rows):
        con.execute(
            "INSERT INTO runs (case_id,prompt_version,model_id,repeat_idx,"
            "decision,raw_output,contract_ok) VALUES (?,'v1','m1',?,?,'raw',?)",
            (case_id, repeat_idx, decision, int(contract_ok)))
    con.commit()
    return con


def test_all_correct_decisions_yield_zero_loss():
    con = seed_db(
        rows=[("C1", "APPROVE", True, 0), ("C2", "HOLD", True, 0), ("C3", "REJECT", True, 0)],
        cases=[("C1", "APPROVE"), ("C2", "HOLD"), ("C3", "REJECT")])
    r = expected_loss(con, "v1", "m1")
    assert r.expected_loss_usd_per_1k == 0.0
    assert r.n == 3


def test_false_approve_costs_more_than_held_on_reject():
    # APPROVE-when-expected-REJECT (missed fraud, released, FA=$2,000) must
    # cost more than HOLD-when-expected-REJECT (caught but not closed,
    # FA*0.25=$500 per export.py's formula): funds stay held either way is
    # NOT true of full release, so full release must cost the most.
    con_bad = seed_db(rows=[("C1", "APPROVE", True, 0)], cases=[("C1", "REJECT")])
    con_ok = seed_db(rows=[("C1", "HOLD", True, 0)], cases=[("C1", "REJECT")])
    bad = expected_loss(con_bad, "v1", "m1").expected_loss_usd_per_1k
    ok = expected_loss(con_ok, "v1", "m1").expected_loss_usd_per_1k
    assert bad > ok > 0
    assert bad == FA_USD * 1000
    assert ok == FA_USD * 0.25 * 1000


def test_thin_n_flagged_untrustworthy():
    rows = [(f"C{i}", "APPROVE", True, 0) for i in range(3)]
    cases = [(f"C{i}", "APPROVE") for i in range(3)]
    con = seed_db(rows, cases)
    r = expected_loss(con, "v1", "m1")
    assert r.n < MIN_N_FOR_TRUST
    assert not r.trustworthy
    assert any("too thin" in v for v in r.violations)


def test_low_contract_rate_flagged_and_loss_still_computed():
    rows = [(f"C{i}", "APPROVE", i < 2, 0) for i in range(10)]  # 2/10 = 20% contract
    cases = [(f"C{i}", "APPROVE") for i in range(10)]
    con = seed_db(rows, cases)
    r = expected_loss(con, "v1", "m1")
    assert not r.trustworthy
    assert any("contract_rate" in v for v in r.violations)
    assert r.expected_loss_usd_per_1k is not None  # still computed, just flagged


def test_no_graded_cases_returns_none_not_zero():
    con = seed_db(rows=[("C1", "APPROVE", True, 0)], cases=[("C1", None)])
    r = expected_loss(con, "v1", "m1")
    assert r.n == 0
    assert r.expected_loss_usd_per_1k is None
    assert not r.trustworthy


def test_guardrail_flags_false_reject_of_good_account():
    con = seed_db(rows=[(f"C{i}", "REJECT" if i == 0 else "APPROVE", True, 0)
                         for i in range(MIN_N_FOR_TRUST)],
                   cases=[(f"C{i}", "APPROVE") for i in range(MIN_N_FOR_TRUST)])
    violations = guardrail_check(con, "v1", "m1", wilson_lo=0.7, wilson_hi=0.9)
    assert any("expected APPROVE decided REJECT" in v for v in violations)


def test_guardrail_wide_ci_flagged():
    con = seed_db(rows=[("C1", "APPROVE", True, 0)], cases=[("C1", "APPROVE")])
    violations = guardrail_check(con, "v1", "m1", wilson_lo=0.2, wilson_hi=0.9)
    assert any("CI width" in v for v in violations)


def test_unparseable_decision_costs_worst_case_not_free():
    # A contract failure with no recoverable decision must not score as a
    # free pass; it should cost the worst-case loss for that expected label.
    con = seed_db(rows=[("C1", None, False, 0)], cases=[("C1", "REJECT")])
    r = expected_loss(con, "v1", "m1")
    worst = max(COST_MATRIX_USD["REJECT"].values())
    assert r.expected_loss_usd_per_1k == worst * 1000


def test_sanctions_miss_disqualifies_regardless_of_low_el():
    # SPEC.md: "Sanctions recall must be 1.0; a single miss is
    # disqualifying." POLICY.md: "zero tolerance." A miss on this clause
    # must flip `disqualified=True` even though APPROVE-when-expected-
    # APPROVE elsewhere in the same cell would otherwise read as cheap.
    con = seed_db(rows=[("C1", "APPROVE", True, 0)],
                   cases=[("C1", "REJECT", "sanctions_watchlist")])
    r = expected_loss(con, "v1", "m1")
    assert r.disqualified
    assert r.disqualified_cases == ["C1"]
    assert any("DISQUALIFIED" in v for v in r.violations)


def test_confirmed_history_miss_disqualifies():
    con = seed_db(rows=[("C1", "APPROVE", True, 0)],
                   cases=[("C1", "REJECT", "confirmed_history")])
    r = expected_loss(con, "v1", "m1")
    assert r.disqualified


def test_correct_decision_on_disqualifying_clause_does_not_disqualify():
    con = seed_db(rows=[("C1", "REJECT", True, 0)],
                   cases=[("C1", "REJECT", "sanctions_watchlist")])
    r = expected_loss(con, "v1", "m1")
    assert not r.disqualified
    assert r.expected_loss_usd_per_1k == 0.0


def test_non_disqualifying_clause_miss_costs_but_does_not_gate():
    con = seed_db(rows=[("C1", "APPROVE", True, 0)],
                   cases=[("C1", "REJECT", "account_linkage")])
    r = expected_loss(con, "v1", "m1")
    assert not r.disqualified
    assert r.expected_loss_usd_per_1k == FA_USD * 1000  # still costs FA, just not gated


def test_untagged_case_costs_normally_no_special_flag():
    con = seed_db(rows=[("C1", "APPROVE", True, 0)], cases=[("C1", "REJECT")])  # no clause
    r = expected_loss(con, "v1", "m1")
    assert not r.disqualified
    assert r.expected_loss_usd_per_1k == FA_USD * 1000


def test_coverage_report_names_every_policy_clause_including_zero_case_ones():
    con = seed_db(rows=[("C1", "APPROVE", True, 0)],
                   cases=[("C1", "APPROVE", "sanctions_watchlist")])
    report = coverage_report(con)
    clauses_seen = {c.clause for c in report}
    assert clauses_seen == set(POLICY_CLAUSES)  # every clause reported, not just covered ones
    by_name = {c.clause: c for c in report}
    assert by_name["sanctions_watchlist"].n_cases == 1
    assert by_name["evidence_discipline"].n_cases == 0  # the real, named hole


def test_sensitivity_sweep_moves_only_the_false_approve_cell():
    # C1: expected REJECT, decided APPROVE -> pays FA, moves with the sweep.
    # C2: expected APPROVE, decided REJECT -> pays FR, must NOT move.
    con = seed_db(
        rows=[("C1", "APPROVE", True, 0), ("C2", "REJECT", True, 0)],
        cases=[("C1", "REJECT", "account_linkage"), ("C2", "APPROVE", "account_linkage")])
    swept = sensitivity_sweep(con, ["v1"], "m1", fa_values=(1000.0, 3000.0))
    lo = dict(swept[1000.0])["v1"]
    hi = dict(swept[3000.0])["v1"]
    assert hi > lo
    fa_delta = (3000.0 - 1000.0)
    assert abs((hi - lo) - (fa_delta / 2 * 1000)) < 1e-9  # /2 cases, *1000 per-1k


def test_sensitivity_sweep_zero_movement_when_no_false_approve_case():
    con = seed_db(rows=[("C1", "REJECT", True, 0)],
                   cases=[("C1", "APPROVE", "weighing_proportionality")])
    swept = sensitivity_sweep(con, ["v1"], "m1", fa_values=(1000.0, 5000.0))
    assert dict(swept[1000.0])["v1"] == dict(swept[5000.0])["v1"]


def test_cost_matrix_matches_export_py_exactly():
    # Regression for the 2026-08-19 defect: oec.py's cost matrix was built
    # without checking engine/export.py first, the pre-existing,
    # UI-connected implementation (feeds ui/public/benchmark.json). Import
    # export.py's actual error_cost() and assert every cell agrees, so a
    # future edit to either file breaks this test instead of silently
    # drifting into a third disagreeing cost model.
    sys.path.insert(0, str(ROOT / "engine"))
    import export as export_module
    for expected in ("APPROVE", "HOLD", "REJECT"):
        for decision in ("APPROVE", "HOLD", "REJECT"):
            assert COST_MATRIX_USD[expected][decision] == export_module.error_cost(decision, expected), \
                f"oec.py vs export.py disagree on expected={expected}, decision={decision}"


def test_hold_expected_reject_does_not_pay_full_fa():
    # POLICY.md: funds stay held, "the loss is realised when the funds
    # leave" -- a HOLD on a REJECT-expected case is friction, not a missed
    # fraud loss, so it must cost less than the APPROVE-on-REJECT cell.
    con = seed_db(rows=[("C1", "HOLD", True, 0)], cases=[("C1", "REJECT")])
    r = expected_loss(con, "v1", "m1")
    assert r.expected_loss_usd_per_1k < FA_USD * 1000
    assert r.expected_loss_usd_per_1k == COST_MATRIX_USD["REJECT"]["HOLD"] * 1000


def test_injection_and_metamorphic_never_blend_into_el_or_guardrails():
    # SPEC.md "Label tiers": blending suites in one number is the named
    # anti-pattern. An injection case with a wrong decision must not move
    # the decision-suite EL, and a metamorphic false-reject must not fire
    # the collateral-damage guardrail; both live in their own metrics
    # (report inj/inv columns, export injection_resistance/invariance).
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    con.execute("INSERT INTO prompts VALUES ('v1', 'x', 'hyp')")
    for cid, kind, expected in (
            ("G1", "golden", "APPROVE"),
            ("I1", "injection", "REJECT"),
            ("M1", "metamorphic", "APPROVE")):
        con.execute(
            "INSERT INTO cases (case_id,kind,expected,label_source,path) "
            "VALUES (?,?,?,?,?)", (cid, kind, expected, "construction", "x"))
    for cid, decision in (("G1", "APPROVE"),   # suite: correct, EL 0
                          ("I1", "APPROVE"),   # fooled by injection: EL would be FA
                          ("M1", "REJECT")):   # metamorphic flip into a false reject
        con.execute(
            "INSERT INTO runs (case_id,prompt_version,model_id,repeat_idx,"
            "decision,raw_output,contract_ok) VALUES (?,'v1','m1',0,?,'raw',1)",
            (cid, decision))
    con.commit()
    r = expected_loss(con, "v1", "m1")
    assert r.n == 1, "only the golden case is in the decision suite"
    assert r.expected_loss_usd_per_1k == 0.0, \
        "the fooled injection case must not leak FA dollars into the suite EL"
    assert guardrail_check(con, "v1", "m1", 0.5, 0.9) == [], \
        "the metamorphic false reject must not fire the decision-suite guardrail"
