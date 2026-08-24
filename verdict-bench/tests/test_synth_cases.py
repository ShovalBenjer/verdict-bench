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
        for k in ("on_hold_usd", "at_risk_usd", "lifetime_volume_usd"):
            assert isinstance(c["money"][k], (int, float))
        assert "status" in c["account"]["verification"]


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
    for c in by_arch["sanctions_true_match"]:
        hit = c["watchlist_hits"][0]
        assert hit["matched_dob"] == c["account"]["owner_dob"]
        assert hit["score"] >= 0.9
    for c in by_arch["watchlist_false_positive"]:
        hit = c["watchlist_hits"][0]
        assert hit["matched_dob"] != c["account"]["owner_dob"]
    for c in by_arch["card_testing"]:
        declined = [t for t in c["transactions"] if t["status"] == "declined"]
        assert len(declined) >= 8
        assert all(t["amount_usd"] < 5 for t in declined)
    for c in by_arch["bust_out"]:
        assert any(t["type"] == "payout_transfer_new_destination"
                   for t in c["transactions"])
        assert c["money"]["at_risk_usd"] > 0
    for c in by_arch["confirmed_prior_fraud"]:
        assert any(p["decision"] == "REJECT" for p in c["prior_cases"])
        assert c["precomputed"]["confirmed_problem_on_record"]
    for c in by_arch["data_quality_flag"]:
        assert c["precomputed"]["confirmed_problem_on_record"]
        assert not any(p.get("decision") == "REJECT" for p in c["prior_cases"])
    for c in by_arch["fraud_linked"]:
        assert any(la["status"] == "CLOSED_FRAUD" for la in c["linked_accounts"])
    for c in by_arch["incidental_overlap"]:
        assert all(la["status"] != "CLOSED_FRAUD" for la in c["linked_accounts"])
    for c in by_arch["unverifiable_identity"]:
        assert c["account"]["verification"]["status"] != "VERIFIED"
        assert c["money"]["at_risk_usd"] > 0
    for c in by_arch["minor_anomaly_established"]:
        assert c["account"]["tenure_days"] >= 500


def test_hold_and_reject_synthetics_expose_money_where_policy_requires():
    # The identity clause hinges on exposure: an unverified party with zero
    # money at risk would NOT be a policy HOLD, so the generator must never
    # emit that combination.
    cases, labels = generate(4)
    for c in cases:
        if labels[c["case_id"]]["archetype"] == "unverifiable_identity":
            assert c["money"]["at_risk_usd"] > 0


def test_archetype_ids_stable():
    # IDs are load-bearing (ledger rows key on them): the first case of the
    # first archetype is CASE-200 forever; renumbering would orphan runs.
    cases, _ = generate(1)
    assert cases[0]["case_id"] == "CASE-200"
    assert len({c["case_id"] for c in cases}) == len(cases)
    assert len(ARCHETYPES) == 13
