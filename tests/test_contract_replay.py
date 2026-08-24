"""Record/replay contract test (the larger-tests chapter's own pattern for
third-party seams): every raw_output string the ledger ever banked from a
real provider is replayed through parse_contract, which must reproduce the
stored (decision, contract_ok) verdict exactly. This is the one test where
parse_contract meets real, non-handcrafted provider text; the ledger is
opened read-only via a temp copy so the test can never mutate the artifact
it certifies."""
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "state" / "verdict.sqlite3"

import sys

sys.path.insert(0, str(ROOT / "engine"))
from providers import parse_contract


@pytest.mark.skipif(not LEDGER.exists(), reason="no banked ledger")
def test_parse_contract_reproduces_every_banked_verdict(tmp_path):
    con = sqlite3.connect(tmp_path / "copy.sqlite3")
    src = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)
    src.backup(con)  # snapshot: a concurrently-writing runner can't torn-read us
    src.close()
    rows = con.execute(
        "SELECT run_id, raw_output, decision, contract_ok FROM runs "
        "WHERE raw_output IS NOT NULL AND error IS NULL").fetchall()
    assert len(rows) > 100  # the replay corpus is real, not a stub
    mismatches = []
    for run_id, raw, decision, contract_ok in rows:
        d, _reasoning, _conf, ok, _err = parse_contract(raw)
        if (d, int(ok)) != (decision, contract_ok):
            mismatches.append((run_id, (d, int(ok)), (decision, contract_ok)))
    assert not mismatches, (
        f"{len(mismatches)}/{len(rows)} banked rows no longer reproduce; "
        f"first: run_id={mismatches[0][0]} replay={mismatches[0][1]} "
        f"banked={mismatches[0][2]}")
