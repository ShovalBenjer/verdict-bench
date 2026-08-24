"""Who grades the grader: planted-defect tests for the contract parser and
the report's aggregation. Each test plants a defect the grader must catch."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
from providers import parse_contract


def test_strict_json_passes():
    d, r, c, ok, err = parse_contract('{"decision": "APPROVE", "reasoning": "x"}')
    assert d == "APPROVE" and ok and err is None


def test_fenced_json_is_contract_violation_but_graded():
    d, _, _, ok, err = parse_contract('```json\n{"decision": "HOLD", "reasoning": "x"}\n```')
    assert d == "HOLD" and not ok  # decision recovered, contract failed
    assert err is None  # recovered decision must not also carry an error string


def test_prose_preamble_is_violation():
    d, _, _, ok, _ = parse_contract('Analysis first.\n{"decision": "REJECT", "reasoning": "y"}')
    assert d == "REJECT" and not ok


def test_truncated_json_yields_no_decision():
    d, _, _, ok, err = parse_contract('{"decision": "APPROVE", "reasoning": "cut off')
    assert d is None and not ok and err


def test_decision_outside_enum_rejected():
    d, _, _, ok, err = parse_contract('{"decision": "ESCALATE", "reasoning": "z"}')
    assert d is None and not ok and "invalid decision" in err


def test_no_json_at_all():
    d, _, _, ok, err = parse_contract("I think this account looks fine.")
    assert d is None and not ok and err


def test_labels_file_covers_every_case_file():
    labels = json.loads((ROOT / "data" / "labels.json").read_text())
    case_ids = {json.loads(p.read_text())["case_id"]
                for p in (ROOT / "data" / "cases").glob("*.json")}
    assert case_ids == set(labels), f"unlabeled cases: {case_ids ^ set(labels)}"


# test_retired_case_never_runs lived here until 2026-08-24. It was vacuous:
# it counted ledger history that could not fail whatever the code did (the
# retired case has zero runs, pinned batch or not). The real oracle, seeding
# a temp DB and calling runner.run() against a retired case through a fake
# provider, is test_pyramid.py::test_retired_case_writes_no_row.


def test_report_runs_clean(tmp_path):
    # Smoke the report against a SNAPSHOT of the ledger, never the tracked
    # file: report() calls migrate(), and a smoke test that can rewrite the
    # deliverable it certifies is the shared-SUT antipattern by the book.
    src = sqlite3.connect(f"file:{ROOT / 'state' / 'verdict.sqlite3'}?mode=ro", uri=True)
    snap = tmp_path / "snap.sqlite3"
    dst = sqlite3.connect(snap)
    src.backup(dst)
    src.close()
    dst.close()
    p = subprocess.run([sys.executable, str(ROOT / "engine" / "runner.py"), "--report"],
                       capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "VERDICT_DB": str(snap)})
    assert p.returncode == 0, p.stderr
