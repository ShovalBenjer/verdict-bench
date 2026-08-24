"""The testing-pyramid batch from the 2026-08-24 standards read
(double_testing.txt + larger_testing.txt): differential, property, and
integration oracles over the real boundaries the unit suite never reached.
No mocks anywhere: real in-memory/temp SQLite built from the real
schema.sql, and one FAKE provider that speaks the real DecisionResult
contract (licensed by the third-party-seam rule; its shape is pinned to a
banked row by test_contract_replay.py's replay over real recorded output).
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

import export as export_mod
import oec
import runner
from judge import judge_for
from providers import PROVIDERS, DecisionResult

SCHEMA = (ROOT / "engine" / "schema.sql").read_text()


def mem_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    return con


def add_case(con, cid, expected, kind="golden", clause=None, path="/nonexistent.json"):
    con.execute("INSERT INTO cases (case_id,kind,expected,label_source,path,policy_clause,retired)"
                " VALUES (?,?,?,?,?,?,0)", (cid, kind, expected, "construction", path, clause))


def add_run(con, cid, pv, mid, decision, correct, repeat_idx=0, contract_ok=1,
            temperature=0.2):
    con.execute(
        "INSERT INTO runs (case_id,prompt_version,model_id,repeat_idx,decision,"
        "reasoning,confidence,raw_output,contract_ok,correct,tokens_in,tokens_out,"
        "latency_ms,error,prompt_sha,case_sha,temperature,batch_id)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, pv, mid, repeat_idx, decision, "r", None, "raw", contract_ok,
         correct, 10, 10, 1000, None, "sha", "csha", temperature, "b1"))


# 1. Differential: export's EL must equal oec's on the same cell, including
# the unparseable-decision row both used to disagree on (oec charged
# worst-case, export silently dropped the row: UI $0 vs report $2,000,000).
def test_export_el_equals_oec_el_including_unparseable(tmp_path, monkeypatch):
    dbfile = tmp_path / "t.sqlite3"
    con = sqlite3.connect(dbfile)
    con.executescript(SCHEMA)
    add_case(con, "CASE-901", "REJECT")
    add_case(con, "CASE-902", "APPROVE")
    add_run(con, "CASE-901", "vX", "m1", None, None, contract_ok=0)  # unparseable
    add_run(con, "CASE-902", "vX", "m1", "APPROVE", 1)
    con.commit()
    oec_el = oec.expected_loss(con, "vX", "m1").expected_loss_usd_per_1k
    out = tmp_path / "bench.json"
    monkeypatch.setattr(export_mod, "DB", dbfile)
    monkeypatch.setattr(export_mod, "OUT", out)
    export_mod.main()
    cell = next(c for c in json.loads(out.read_text())["cells"]
                if c["prompt"] == "vX" and c["model"] == "m1")
    assert cell["expected_loss_per_1k"] == round(oec_el), (
        f"export says {cell['expected_loss_per_1k']}, oec says {oec_el}")
    assert oec_el == pytest.approx(1_000_000)  # worst-of-REJECT averaged over 2


# 2. cell_trust precedence and the flip guardrail branch.
def test_disq_beats_flag_when_both_apply():
    con = mem_db()
    add_case(con, "CASE-910", "REJECT", clause="sanctions_watchlist")
    add_run(con, "CASE-910", "vX", "m1", "APPROVE", 0)  # zero-tolerance miss
    trust, violations, _ = oec.cell_trust(con, "vX", "m1", 0.0, 1.0, None)
    assert trust == "DISQ"  # thin n and wide CI must not soften it to FLAG
    assert any("DISQUALIFIED" in v for v in violations)


def test_flip_over_threshold_flags_cell():
    con = mem_db()
    for i in range(oec.MIN_N_FOR_TRUST):
        add_case(con, f"CASE-92{i}", "APPROVE")
        add_run(con, f"CASE-92{i}", "vX", "m1", "APPROVE", 1)
    ok, _, _ = oec.cell_trust(con, "vX", "m1", 0.8, 0.99, oec.MAX_FLIP - 0.01)
    bad, viol, _ = oec.cell_trust(con, "vX", "m1", 0.8, 0.99, oec.MAX_FLIP + 0.01)
    assert ok == "ok"
    assert bad == "FLAG"
    assert any("flip" in v.lower() for v in viol)


# 4. judge_for: primary assignment is cross-family for every registered
# model; overlap adds at most one same-family judge and never loses the
# cross-family one (the documented agreement-measurement exception).
def test_judge_for_primary_never_same_family():
    for mid in list(PROVIDERS) + ["m-other"]:
        fam = mid.split("-")[0]
        for j in judge_for(mid, overlap=False):
            assert not j.startswith(fam), f"{mid} judged by same-family {j}"


def test_judge_for_overlap_keeps_cross_family_judge():
    for mid in list(PROVIDERS):
        fam = mid.split("-")[0]
        js = judge_for(mid, overlap=True)
        assert any(not j.startswith(fam) for j in js)


# 5. migrate(): row-preserving and idempotent on an old-schema DB.
def test_migrate_preserves_rows_and_is_idempotent():
    con = sqlite3.connect(":memory:")
    con.executescript(
        "CREATE TABLE cases (case_id TEXT PRIMARY KEY,"
        " kind TEXT NOT NULL CHECK (kind IN ('golden','perturbation','metamorphic','injection','synthetic')),"
        " expected TEXT, label_source TEXT, path TEXT, retired INTEGER NOT NULL DEFAULT 0);")
    con.execute("INSERT INTO cases (case_id,kind,expected,label_source,path) "
                "VALUES ('CASE-1','golden','APPROVE','expert','/x.json')")
    con.commit()
    runner.migrate(con)
    runner.migrate(con)  # second run must be a no-op, not a crash
    assert con.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 1
    con.execute("INSERT INTO cases (case_id,kind,expected,label_source,path,retired)"
                " VALUES ('CASE-2','holdout','HOLD','construction','/y.json',0)")


# 6 + retired-case fix: run() through a fake provider on a temp DB. The fake
# speaks the real DecisionResult contract; shape pinned by the replay test.
def fake_provider(sys_prompt, case_json, temperature=0.2):
    return DecisionResult("APPROVE", "fake reasoning", None,
                          '{"decision":"APPROVE"}', True, 5, 5, 1, None)


@pytest.fixture()
def temp_runner_db(tmp_path, monkeypatch):
    dbfile = tmp_path / "runner.sqlite3"
    monkeypatch.setattr(runner, "DB", dbfile)
    PROVIDERS["fake-test"] = fake_provider
    yield dbfile
    del PROVIDERS["fake-test"]


def test_repeat_idx_offsets_instead_of_colliding(temp_runner_db):
    runner.run("v1", ["fake-test"], repeats=1, only_case="CASE-101")
    runner.run("v1", ["fake-test"], repeats=1, only_case="CASE-101")
    con = sqlite3.connect(temp_runner_db)
    idxs = [r[0] for r in con.execute(
        "SELECT repeat_idx FROM runs WHERE case_id='CASE-101' ORDER BY repeat_idx")]
    assert idxs == [0, 1]  # second invocation offsets, never UNIQUE-collides


def test_retired_case_writes_no_row(temp_runner_db):
    # The real oracle for the retired filter: point run() at the one retired
    # case and assert nothing lands (the old ledger-history version of this
    # test was vacuous: it could not fail whatever the code did).
    retired = [cid for cid, lab in runner.LABELS.items() if lab.get("retired")]
    assert retired, "corpus no longer has a retired case; retire one or drop this test"
    runner.run("v1", ["fake-test"], repeats=1, only_case=retired[0])
    con = sqlite3.connect(temp_runner_db)
    assert con.execute("SELECT COUNT(*) FROM runs WHERE case_id=?",
                       (retired[0],)).fetchone()[0] == 0


# 7. report() suppresses the dollar figure on an untrusted cell.
def test_report_prints_untrust_not_dollars_on_thin_cell(tmp_path, monkeypatch, capsys):
    dbfile = tmp_path / "r.sqlite3"
    con = sqlite3.connect(dbfile)
    con.executescript(SCHEMA)
    add_case(con, "CASE-930", "REJECT")
    add_run(con, "CASE-930", "vX", "m1", "APPROVE", 0)  # huge loss, n=1
    con.commit()
    monkeypatch.setattr(runner, "DB", dbfile)
    runner.report()
    line = next(ln for ln in capsys.readouterr().out.splitlines()
                if ln.startswith("vX"))
    assert "untrust" in line
    assert "2000000" not in line.replace(",", "")


# 8. Corpus invariants: every disqualifying clause has a live case behind
# it, and NO non-suite kind can leak into EL (all four, not just two).
def test_every_disqualifying_clause_has_a_live_case():
    labels = json.loads((ROOT / "data" / "labels.json").read_text())
    for clause in oec.DISQUALIFYING_CLAUSES:
        live = [cid for cid, lab in labels.items()
                if lab.get("policy_clause") == clause and not lab.get("retired")]
        assert live, f"gate clause {clause} has no non-retired case exercising it"


@pytest.mark.parametrize("kind", ["injection", "metamorphic", "coverage", "holdout", "synthetic"])
def test_no_nonsuite_kind_leaks_into_el(kind):
    con = mem_db()
    add_case(con, "CASE-940", "APPROVE")
    add_run(con, "CASE-940", "vX", "m1", "APPROVE", 1)
    base = oec.expected_loss(con, "vX", "m1")
    add_case(con, "CASE-941", "REJECT", kind=kind)
    add_run(con, "CASE-941", "vX", "m1", "APPROVE", 0)  # would be a huge loss
    after = oec.expected_loss(con, "vX", "m1")
    assert after.expected_loss_usd_per_1k == base.expected_loss_usd_per_1k
    assert after.n == base.n


# SPRT: the sequential stopping rule stops early in BOTH directions and
# never crosses a boundary on ambiguous evidence.
def test_sprt_rejects_a_clearly_losing_challenger_early():
    verdict, _, n = oec.sprt([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    assert verdict == "reject"
    assert n < 12  # stopped before burning the whole suite


def test_sprt_accepts_a_clean_sweep():
    verdict, _, n = oec.sprt([1] * 30)
    assert verdict == "accept"


def test_sprt_continues_inside_the_indifference_region():
    # 5/6 (~0.83) sits between p0=0.75 and p1=0.92: neither boundary may
    # trip. (An alternating 50% stream is NOT ambiguous under these params:
    # the failure log-term is ~5x the success term, so it rejects fast,
    # which the first draft of this test got wrong.)
    verdict, _, n = oec.sprt([1, 1, 1, 1, 1, 0])
    assert verdict == "continue"
    assert n == 6


def test_sprt_rejects_bad_hypothesis_ordering():
    with pytest.raises(ValueError):
        oec.sprt([1], p0=0.9, p1=0.5)
