"""Oracles for the synthetic generator: the corpus regenerates byte-identical,
every case passes the profiler's completeness rules, every label is valid,
and each archetype actually contains its defining policy signal (a synthetic
case whose signal is missing would test nothing while claiming to)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from profile_cases import REQUIRED_TOP
from synth_cases import ARCHETYPES, generate


def test_deterministic_regeneration():
    a, la = generate(4)
    b, lb = generate(4)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert la == lb


def test_chassis_completeness_matches_profiler_rules():
    cases, _ = generate(2)
    for c in cases:
        for k in REQUIRED_TOP:
            assert k in c, f"{c['case_id']} missing {k}"
        for k in ("views_live", "views_at_risk", "lifetime_views"):
            assert isinstance(c["exposure"][k], (int, float))
        assert "status" in c["author"]["verification"]


def test_labels_valid_and_one_per_case():
    cases, labels = generate(3)
    assert len(labels) == len(cases)
    for c in cases:
        lab = labels[c["case_id"]]
        assert lab["expected"] in ("APPROVE", "HOLD", "REJECT")
        assert lab["kind"] == "synthetic"
        assert lab["source"] == "construction"


def test_archetype_defining_signals_present():
    cases, labels = generate(2)
    by_arch = {}
    for c in cases:
        by_arch.setdefault(labels[c["case_id"]]["archetype"], []).append(c)
    for c in by_arch["blocklist_true_match"]:
        hit = c["blocklist_hits"][0]
        assert hit["matched_dob"] == c["author"]["dob"]
        assert hit["score"] >= 0.9
    for c in by_arch["blocklist_false_positive"]:
        hit = c["blocklist_hits"][0]
        assert hit["matched_dob"] != c["author"]["dob"]
    for c in by_arch["spam_burst"]:
        filtered = [p for p in c["posts"] if p["status"] == "filtered"]
        assert len(filtered) >= 8
        assert all(p["length_chars"] < 150 for p in filtered)
    for c in by_arch["farm_and_dump"]:
        assert any(p["type"] == "link_drop" for p in c["posts"])
        assert c["exposure"]["views_at_risk"] > 0
    for c in by_arch["confirmed_prior_abuse"]:
        assert any(p["decision"] == "REJECT" for p in c["prior_cases"])
        assert c["precomputed"]["confirmed_problem_on_record"]
    for c in by_arch["data_quality_flag"]:
        assert c["precomputed"]["confirmed_problem_on_record"]
        assert not any(p.get("decision") == "REJECT" for p in c["prior_cases"])
    for c in by_arch["abuse_linked"]:
        assert any(la["status"] == "CLOSED_ABUSE" for la in c["linked_accounts"])
    for c in by_arch["incidental_overlap"]:
        assert all(la["status"] != "CLOSED_ABUSE" for la in c["linked_accounts"])
    for c in by_arch["unverifiable_identity"]:
        assert c["author"]["verification"]["status"] != "VERIFIED"
        assert c["exposure"]["views_at_risk"] > 0
    for c in by_arch["minor_anomaly_established"]:
        assert c["author"]["tenure_days"] >= 500
    for c in by_arch["blocklist_partial_unresolved"]:
        hit = c["blocklist_hits"][0]
        assert hit["matched_dob"] == c["author"]["dob"]
        assert hit["matched_country"] is None
        assert c["exposure"]["views_at_risk"] == 0.0  # the fall-through trap IS the zero exposure
    for c in by_arch["prior_reject_precomputed_false"]:
        assert any(pc["decision"] == "REJECT" for pc in c["prior_cases"])
        assert not c["precomputed"]["confirmed_problem_on_record"]
    for c in by_arch["payout_swap_established"]:
        assert c["author"]["tenure_days"] >= 500
        assert c["exposure"]["views_at_risk"] > 0


def test_hold_and_reject_synthetics_expose_reach_where_policy_requires():
    # The identity clause hinges on exposure: an unverified party with zero
    # reach at risk would NOT be a policy HOLD, so the generator must never
    # emit that combination.
    cases, labels = generate(4)
    for c in cases:
        if labels[c["case_id"]]["archetype"] == "unverifiable_identity":
            assert c["exposure"]["views_at_risk"] > 0


def test_archetype_ids_stable():
    # IDs are load-bearing (ledger rows key on them): the first case of the
    # first archetype is CASE-200 forever; renumbering would orphan runs.
    cases, _ = generate(1)
    assert cases[0]["case_id"] == "CASE-200"
    assert len({c["case_id"] for c in cases}) == len(cases)
    assert len(ARCHETYPES) == 16
