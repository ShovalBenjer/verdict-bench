"""Executable half of docs/JUDGE-BIAS.md: the bias mitigations that can be
checked without spending a judge call. The probes themselves need the live
judge; what this file pins down is that the mitigations and the fixture have
not silently rotted."""
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "judge_adversarial.jsonl"
sys.path.insert(0, str(ROOT / "engine"))
import judge

MODELS = ["claude-haiku", "claude-sonnet-v4", "gemini-flash", "gemini-pro",
          "llama-3-70b", "nemotron-70b", "qwen-2-72b", "hf-phi-4"]

# Decisive case fields the fidelity axis requires a reasoning to cite.
DECISIVE_TOKENS = ("blocklist", "views_at_risk", "confirmed_problem", "prior_cases",
                   "session_history", "posts", "views_live")


def _probes():
    return [json.loads(line) for line in FIX.read_text().splitlines()
            if line.strip()]


def test_cross_family_primary():
    # Self-preference mitigation: no judged model ever gets a same-family judge.
    for m in MODELS:
        fam = m.split("-")[0]
        for j in judge.judge_for(m):
            assert not j.startswith(fam), f"{m} judged by same-family {j}"


def test_overlap_keeps_cross_family_judge_first():
    # The overlap exception adds a same-family judge for agreement measurement,
    # but the cross-family judge must always be present alongside it.
    js = judge.judge_for("gemini-flash", overlap=True)
    assert len(js) > 1
    assert not js[0].startswith("gemini")
    assert any(j.startswith("gemini") for j in js[1:])


def test_rubric_version_pinned():
    # A silent rubric change invalidates every historical comparison.
    assert judge.RUBRIC_VERSION == "r1"


def test_adversarial_fixture_shape():
    rows = _probes()
    assert len(rows) >= 5
    for r in rows:
        assert {"id", "target_axis", "max_expected", "reasoning"} <= set(r)
        assert r["target_axis"] in ("fidelity", "evidence", "proportionality")
        assert 1 <= r["max_expected"] <= 2


def test_length_trap_is_long_and_vacuous():
    # The length-bias probe only works if it is long enough to tempt a
    # length-biased judge AND cites nothing decisive.
    row = next(r for r in _probes() if r["id"] == "length-trap")
    words = len(row["reasoning"].split())
    assert words >= 250, f"length-trap too short to tempt: {words} words"
    lowered = row["reasoning"].lower()
    cited = [t for t in DECISIVE_TOKENS if t in lowered]
    assert not cited, f"length-trap accidentally cites decisive fields: {cited}"


def test_judge_rejects_out_of_range_scores(monkeypatch):
    # A judge returning 6/5 is a contract violation; it must be recorded as a
    # parse failure, never averaged into the ledger.
    fake = types.SimpleNamespace(
        raw_output='{"fidelity": 6, "evidence": 5, "proportionality": 5, '
                   '"rationale": "off the scale"}')
    monkeypatch.setattr(judge, "call_gemini", lambda *a: fake)
    scores, raw = judge.call_judge("gemini-flash", "whatever")
    assert scores is None and raw == fake.raw_output


def test_judge_accepts_valid_scores(monkeypatch):
    fake = types.SimpleNamespace(
        raw_output='{"fidelity": 4, "evidence": 3, "proportionality": 5, '
                   '"rationale": "cites the watchlist hit and weighs exposure"}')
    monkeypatch.setattr(judge, "call_gemini", lambda *a: fake)
    scores, _ = judge.call_judge("gemini-flash", "whatever")
    assert scores == {"fidelity": 4.0, "evidence": 3.0, "proportionality": 5.0}
