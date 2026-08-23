"""Who grades the grader: planted-defect tests for the contract parser and
the report's aggregation. Each test plants a defect the grader must catch."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
from providers import parse_contract  # noqa: E402


def test_strict_json_passes():
    d, r, c, ok, err = parse_contract('{"decision": "APPROVE", "reasoning": "x"}')
    assert d == "APPROVE" and ok and err is None


def test_fenced_json_is_contract_violation_but_graded():
    d, _, _, ok, err = parse_contract('```json\n{"decision": "HOLD", "reasoning": "x"}\n```')
    assert d == "HOLD" and not ok  # decision recovered, contract failed


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


def test_retired_case_never_runs():
    con = sqlite3.connect(ROOT / "state" / "verdict.sqlite3")
    rows = con.execute(
        "SELECT COUNT(*) FROM runs r JOIN cases c USING(case_id) "
        "WHERE c.retired=1 AND r.batch_id IS NOT NULL").fetchone()[0]
    assert rows == 0, "retired case appeared in a pinned batch"


def test_report_runs_clean():
    p = subprocess.run([sys.executable, str(ROOT / "engine" / "runner.py"), "--report"],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
