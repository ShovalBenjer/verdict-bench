#!/usr/bin/env python3
"""Synthetic case generator: 12 archetypes x N seeded variants.

Each archetype is ONE policy clause instantiated as a case template, so the
label is construction-derived: it holds by how the case was built, not by
expert judgment. That circularity is the point and the limit at once. What
synthetic cases measure is rule-consistency at scale (does the prompt apply
the clause it was written against, across surface variation it has never
seen), NOT expert agreement. They carry kind='synthetic', source=
'construction', and the suite separation in engine/oec.py keeps them out of
headline accuracy and expected loss; they get their own panel.

Determinism: every field derives from random.Random(BASE_SEED + case index),
so the corpus regenerates byte-identical. Run:
  python3 tools/synth_cases.py            # dry run: profile of what would be written
  python3 tools/synth_cases.py --write    # write cases + merge labels.json
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases"
LABELS_PATH = ROOT / "data" / "labels.json"
BASE_SEED = 20260824
FIRST_ID = 200

FIRST = ["Dana", "Omar", "Lea", "Tomas", "Priya", "Ken", "Sofia", "Yuri",
         "Amara", "Felix", "Noa", "Ravi", "Ines", "Marco", "Tal", "Aisha"]
LAST = ["Feld", "Haddad", "Kimura", "Novak", "Osei", "Petrov", "Quinn",
        "Rossi", "Stein", "Toledo", "Ueda", "Vega", "Weiss", "Yona", "Zamir"]
CITIES = ["Denver, US", "Portland, US", "Columbus, US", "Raleigh, US",
          "Tucson, US", "Omaha, US", "Boise, US", "Richmond, US"]
MCCS = ["5462", "5812", "5945", "7299", "5734", "5699", "5941", "7538"]
BIZ = ["Studio", "Supply Co", "Works", "Trading LLC", "Services", "Labs",
       "Goods", "Collective"]


def _mk(rng: random.Random, cid: str, tenure: int, verified: bool,
        opened: str) -> dict:
    """The neutral chassis every archetype starts from."""
    first, last = rng.choice(FIRST), rng.choice(LAST)
    return {
        "case_id": cid,
        "flag_reason": "RISK_REVIEW",
        "opened": opened,
        "priority": rng.choice(["low", "medium", "high"]),
        "account": {
            "account_id": f"ACC-{rng.randint(10000, 99999)}",
            "owner_name": f"{first} {last}",
            "owner_dob": f"19{rng.randint(70, 99)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "owner_ssn_last4": f"{rng.randint(1000, 9999)}",
            "owner_country": "US",
            "business_name": f"{last} {rng.choice(BIZ)}",
            "mcc": rng.choice(MCCS),
            "tenure_days": tenure,
            "verification": {
                "status": "VERIFIED" if verified else "PENDING",
                "kyc_completed": verified,
                "kyb_completed": verified,
                "vendor_reports": [],
            },
        },
        "money": {"on_hold_usd": 0.0, "at_risk_usd": 0.0,
                  "current_balance_usd": round(rng.uniform(200, 6000), 2),
                  "lifetime_volume_usd": round(tenure * rng.uniform(40, 220), 2)},
        "precomputed": {"confirmed_problem_on_record": False,
                        "prior_verified_issue": False},
        "watchlist_hits": [],
        "device_login_history": [
            {"date": (date.fromisoformat(opened) - timedelta(days=d)).isoformat(),
             "ip": f"72.{rng.randint(10, 99)}.{rng.randint(1, 250)}.{rng.randint(1, 250)}",
             "device_id": f"dev-{rng.randint(100, 999)}",
             "geo": rng.choice(CITIES), "note": ""}
            for d in sorted(rng.sample(range(1, 40), 3), reverse=True)
        ],
        "transactions": [],
        "linked_accounts": [],
        "prior_cases": [],
        "notes": [],
    }


def _sales(rng: random.Random, opened: str, n: int, lo: float, hi: float,
           declines: int = 0) -> list[dict]:
    txs = []
    d0 = date.fromisoformat(opened)
    for i in range(n):
        amt = round(rng.uniform(lo, hi), 2)
        ok = i >= declines
        txs.append({
            "date": (d0 - timedelta(days=rng.randint(2, 60))).isoformat(),
            "time": f"{rng.randint(8, 20):02d}:{rng.randint(0, 59):02d}:00",
            "amount_usd": amt, "status": "approved" if ok else "declined",
            "settled_amount_usd": amt if ok else 0.0,
            "instrument_last4": f"{rng.randint(1000, 9999)}",
            "bin": f"{rng.randint(40, 55)}0000", "type": "card_auth"})
    txs.sort(key=lambda t: (t["date"], t["time"]))
    return txs


# Each archetype: (policy_clause, expected, builder). The builder mutates the
# chassis so the clause's defining signal is present, plus benign noise.
def a_clean_established(rng, c, opened):
    c["transactions"] = _sales(rng, opened, 8, 30, 400, declines=1)
    c["flag_reason"] = "VELOCITY_REVIEW"
    c["notes"].append({"author": "screening_system", "date": opened,
                       "text": "Routine periodic review; volume within profile."})
    return c


def a_watchlist_false_positive(rng, c, opened):
    c["flag_reason"] = "WATCHLIST_NAME_MATCH"
    c["transactions"] = _sales(rng, opened, 6, 25, 300)
    c["watchlist_hits"] = [{
        "list": "GLOBAL_SANCTIONS", "matched_name": c["account"]["owner_name"],
        "match_type": "name_only",
        "matched_dob": f"19{rng.randint(40, 60)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        "matched_country": rng.choice(["IR", "SY", "VE"]),
        "score": round(rng.uniform(0.5, 0.7), 2)}]
    c["account"]["verification"]["vendor_reports"].append({
        "vendor": "IDVerifyPlus", "result": "PASS",
        "detail": f"Government ID, SSN, and DOB verified for {c['account']['owner_name']}, "
                  f"DOB {c['account']['owner_dob']}, US."})
    return c


def a_sanctions_true_match(rng, c, opened):
    c["flag_reason"] = "WATCHLIST_NAME_MATCH"
    c["transactions"] = _sales(rng, opened, 5, 50, 600)
    c["watchlist_hits"] = [{
        "list": "GLOBAL_SANCTIONS", "matched_name": c["account"]["owner_name"],
        "match_type": "name_dob_country",
        "matched_dob": c["account"]["owner_dob"], "matched_country": "US",
        "score": round(rng.uniform(0.93, 0.99), 2)}]
    c["account"]["verification"]["vendor_reports"].append({
        "vendor": "SanctionsScreenCo", "result": "CONFIRMED_MATCH",
        "detail": "Identity attributes compared: DOB and country align with the listed entry."})
    return c


def a_card_testing(rng, c, opened):
    c["flag_reason"] = "AUTH_PATTERN"
    d0 = date.fromisoformat(opened) - timedelta(days=rng.randint(1, 3))
    minute = rng.randint(0, 20)
    txs = []
    for i in range(14):
        txs.append({"date": d0.isoformat(),
                    "time": f"{rng.randint(1, 4):02d}:{(minute + i) % 60:02d}:00",
                    "amount_usd": round(rng.uniform(0.5, 2.5), 2),
                    "status": "declined" if i < 11 else "approved",
                    "settled_amount_usd": 0.0,
                    "instrument_last4": f"{rng.randint(1000, 9999)}",
                    "bin": f"{rng.randint(40, 55)}0000", "type": "card_auth"})
    c["transactions"] = txs
    return c


def a_bust_out(rng, c, opened):
    c["flag_reason"] = "VELOCITY_REVIEW"
    d0 = date.fromisoformat(opened)
    txs = []
    for i in range(9):
        amt = round(rng.uniform(800, 3200), 2)
        txs.append({"date": (d0 - timedelta(days=12 - i)).isoformat(),
                    "time": f"{rng.randint(9, 22):02d}:{rng.randint(0, 59):02d}:00",
                    "amount_usd": amt, "status": "approved",
                    "settled_amount_usd": amt,
                    "instrument_last4": f"{rng.randint(1000, 9999)}",
                    "bin": f"{rng.randint(40, 55)}0000", "type": "card_auth"})
    total = round(sum(t["amount_usd"] for t in txs) * rng.uniform(0.9, 0.98), 2)
    txs.append({"date": (d0 - timedelta(days=1)).isoformat(), "time": "03:40:00",
                "amount_usd": total, "status": "approved",
                "settled_amount_usd": total, "instrument_last4": "",
                "bin": "", "type": "payout_transfer_new_destination"})
    c["transactions"] = txs
    c["money"]["at_risk_usd"] = total
    c["notes"].append({"author": "screening_system", "date": opened,
                       "text": "Payout destination added 2 days before transfer; no prior payout history."})
    return c


def a_unverifiable_identity(rng, c, opened):
    c["flag_reason"] = "KYC_REVIEW"
    c["transactions"] = _sales(rng, opened, 4, 100, 900)
    c["money"]["at_risk_usd"] = round(rng.uniform(4000, 18000), 2)
    c["money"]["on_hold_usd"] = c["money"]["at_risk_usd"]
    c["account"]["verification"]["vendor_reports"].append({
        "vendor": "IDVerifyPlus", "result": "FAIL",
        "detail": "Submitted document did not match issuing-authority record; resubmission requested."})
    return c


def a_doc_inconsistency_new(rng, c, opened):
    c["flag_reason"] = "DOC_REVIEW"
    c["transactions"] = _sales(rng, opened, 3, 60, 500)
    c["money"]["at_risk_usd"] = round(rng.uniform(2000, 9000), 2)
    c["account"]["verification"]["vendor_reports"] += [
        {"vendor": "IDVerifyPlus", "result": "PASS",
         "detail": "ID document passed automated checks."},
        {"vendor": "BizRegistryCheck", "result": "MISMATCH",
         "detail": "Registered business address differs from application; officer list does not include the account owner."}]
    return c


def a_confirmed_prior_fraud(rng, c, opened):
    c["flag_reason"] = "PRIOR_CASE_REVIEW"
    c["transactions"] = _sales(rng, opened, 5, 40, 350)
    c["precomputed"] = {"confirmed_problem_on_record": True,
                        "prior_verified_issue": True}
    c["prior_cases"] = [{
        "case_id": f"CX-{rng.randint(30000, 49999)}",
        "date": (date.fromisoformat(opened) - timedelta(days=rng.randint(200, 600))).isoformat(),
        "decision": "REJECT", "reviewer": f"analyst_{rng.choice(['rk', 'mm', 'ds'])}",
        "note": "Chargeback fraud adjudicated against this party; identity verified at the time."}]
    return c


def a_data_quality_flag(rng, c, opened):
    c["flag_reason"] = "PRIOR_CASE_REVIEW"
    c["transactions"] = _sales(rng, opened, 5, 40, 350)
    c["money"]["at_risk_usd"] = round(rng.uniform(1500, 7000), 2)
    c["precomputed"] = {"confirmed_problem_on_record": True,
                        "prior_verified_issue": False}
    c["notes"].append({"author": "data_migration_bot",
                       "date": (date.fromisoformat(opened) - timedelta(days=90)).isoformat(),
                       "text": "Flag imported from legacy system; source record not migrated."})
    return c


def a_sanctions_partial_unresolved(rng, c, opened):
    # The adversarial-review probe (2026-08-24): DOB matches the listed
    # entry, country is null, and NOTHING is at risk. A prompt whose HOLD
    # gate requires money exposed can fall through to APPROVE here, which
    # releases a possibly-sanctioned party because their balance is low.
    c["flag_reason"] = "WATCHLIST_NAME_MATCH"
    c["transactions"] = _sales(rng, opened, 4, 25, 200)
    c["money"]["at_risk_usd"] = 0.0
    c["money"]["on_hold_usd"] = 0.0
    c["watchlist_hits"] = [{
        "list": "GLOBAL_SANCTIONS", "matched_name": c["account"]["owner_name"],
        "match_type": "name_dob",
        "matched_dob": c["account"]["owner_dob"], "matched_country": None,
        "score": round(rng.uniform(0.78, 0.88), 2)}]
    c["notes"].append({"author": "screening_system", "date": opened,
                       "text": "DOB matches listed entry; listed country field empty at source. Not yet human-reviewed."})
    return c


def a_prior_reject_precomputed_false(rng, c, opened):
    # Second probe: a REAL adjudicated REJECT in prior_cases while the
    # precomputed boolean says false. Derived metadata must not be
    # exculpatory: the record itself is decisive.
    c["flag_reason"] = "PRIOR_CASE_REVIEW"
    c["transactions"] = _sales(rng, opened, 5, 40, 350)
    c["money"]["at_risk_usd"] = round(rng.uniform(1000, 5000), 2)
    c["precomputed"] = {"confirmed_problem_on_record": False,
                        "prior_verified_issue": False}
    c["prior_cases"] = [{
        "case_id": f"CX-{rng.randint(30000, 49999)}",
        "date": (date.fromisoformat(opened) - timedelta(days=rng.randint(150, 500))).isoformat(),
        "decision": "REJECT", "reviewer": f"analyst_{rng.choice(['rk', 'mm'])}",
        "note": "Bust-out adjudicated against this party; same SSN and payout account."}]
    c["notes"].append({"author": "data_migration_bot",
                       "date": (date.fromisoformat(opened) - timedelta(days=30)).isoformat(),
                       "text": "Precomputed risk booleans regenerated during migration; may lag the case record."})
    return c


def a_payout_swap_established(rng, c, opened):
    # Third probe (the reviewer's 108-perturbation): long clean history,
    # but the payout destination changed days ago and is unverified, with
    # real money staged. Tenure attaches to the party IN CONTROL; the
    # control-change cluster is the unresolved question.
    c["flag_reason"] = "PAYOUT_CHANGE_REVIEW"
    c["transactions"] = _sales(rng, opened, 8, 40, 400)
    c["money"]["at_risk_usd"] = round(rng.uniform(4000, 12000), 2)
    d0 = date.fromisoformat(opened)
    c["notes"].append({"author": "screening_system",
                       "date": (d0 - timedelta(days=rng.randint(3, 6))).isoformat(),
                       "text": "Payout bank account replaced; new destination unverified. Login from new device and new geography same week."})
    c["device_login_history"].append({
        "date": (d0 - timedelta(days=rng.randint(2, 5))).isoformat(),
        "ip": f"185.{rng.randint(10, 99)}.{rng.randint(1, 250)}.{rng.randint(1, 250)}",
        "device_id": f"dev-{rng.randint(100, 999)}", "geo": "Nicosia, CY",
        "note": "new device, new geography"})
    return c


def a_minor_anomaly_established(rng, c, opened):
    c["flag_reason"] = "DISPUTE_RATE"
    c["transactions"] = _sales(rng, opened, 10, 20, 250, declines=2)
    c["notes"].append({"author": "screening_system", "date": opened,
                       "text": f"Dispute rate {round(rng.uniform(1.1, 1.6), 1)}% vs "
                               f"{round(rng.uniform(0.8, 1.0), 1)}% trailing average; amounts small."})
    return c


def a_fraud_linked(rng, c, opened):
    c["flag_reason"] = "LINK_ANALYSIS"
    c["transactions"] = _sales(rng, opened, 5, 60, 500)
    c["money"]["at_risk_usd"] = round(rng.uniform(3000, 12000), 2)
    c["linked_accounts"] = [{
        "account_id": f"ACC-{rng.randint(10000, 99999)}",
        "relationship": "same_owner_ssn_and_bank_account",
        "status": "CLOSED_FRAUD",
        "note": "Same SSN and payout bank account as an account closed for bust-out fraud."}]
    return c


def a_incidental_overlap(rng, c, opened):
    c["flag_reason"] = "LINK_ANALYSIS"
    c["transactions"] = _sales(rng, opened, 7, 30, 300)
    c["linked_accounts"] = [{
        "account_id": f"ACC-{rng.randint(10000, 99999)}",
        "relationship": "shared_coworking_address",
        "status": "OPEN_GOOD_STANDING",
        "note": "Same registered coworking address; no shared identity, bank, or device attributes."}]
    return c


def a_probe_then_scale(rng, c, opened):
    c["flag_reason"] = "AUTH_PATTERN"
    d0 = date.fromisoformat(opened)
    txs = []
    for i in range(6):
        txs.append({"date": (d0 - timedelta(days=20 - i)).isoformat(),
                    "time": f"{rng.randint(2, 5):02d}:{rng.randint(0, 59):02d}:00",
                    "amount_usd": round(rng.uniform(0.5, 3.0), 2),
                    "status": "declined" if i < 4 else "approved",
                    "settled_amount_usd": 0.0,
                    "instrument_last4": f"{rng.randint(1000, 9999)}",
                    "bin": f"{rng.randint(40, 55)}0000", "type": "card_auth"})
    for i in range(4):
        amt = round(rng.uniform(900, 2400), 2)
        txs.append({"date": (d0 - timedelta(days=6 - i)).isoformat(),
                    "time": f"{rng.randint(9, 21):02d}:{rng.randint(0, 59):02d}:00",
                    "amount_usd": amt, "status": "approved",
                    "settled_amount_usd": amt,
                    "instrument_last4": f"{rng.randint(1000, 9999)}",
                    "bin": f"{rng.randint(40, 55)}0000", "type": "card_auth"})
    c["transactions"] = txs
    c["money"]["at_risk_usd"] = round(sum(t["settled_amount_usd"] for t in txs), 2)
    return c


ARCHETYPES = [
    # (name, builder, tenure range, verified, expected, policy_clause, cite)
    ("clean_established", a_clean_established, (400, 1200), True, "APPROVE",
     "weighing_proportionality", "ordinary sales, however large or fast-growing, are not a concern"),
    ("watchlist_false_positive", a_watchlist_false_positive, (300, 900), True, "APPROVE",
     "sanctions_watchlist", "a hit that does not hold up as the same individual is not, in itself, a concern"),
    ("sanctions_true_match", a_sanctions_true_match, (100, 700), True, "REJECT",
     "sanctions_watchlist", "a genuine sanctions match is disqualifying"),
    ("card_testing", a_card_testing, (10, 90), False, "REJECT",
     "transaction_activity", "systematic testing of payment credentials... are fraud"),
    ("bust_out", a_bust_out, (20, 120), True, "REJECT",
     "transaction_activity", "the rapid build-up and extraction of funds to an unestablished destination (a bust-out), are fraud"),
    ("unverifiable_identity", a_unverifiable_identity, (15, 120), False, "HOLD",
     "identity_ownership", "where the party... cannot presently be established and money is exposed, the risk is unresolved"),
    ("doc_inconsistency_new", a_doc_inconsistency_new, (10, 80), True, "HOLD",
     "weighing_proportionality", "several unexplained concerns together can be enough to treat an account as unresolved"),
    ("confirmed_prior_fraud", a_confirmed_prior_fraud, (200, 800), True, "REJECT",
     "confirmed_history", "a confirmed, adjudicated problem against the same party is disqualifying"),
    # CONTESTED LABEL (2026-08-24, found by the first synthetic sweep): the
    # policy supports HOLD ("where genuine doubt remains and money is
    # exposed, holding is preferred") AND APPROVE (the flag conflicts with
    # the record on a verified, established account, mirroring CASE-115's
    # accepted APPROVE at $150 exposure). v1 decides HOLD 4/4, v5 APPROVE
    # 4/4: a stable cross-version split, which per the feedback-loop design
    # is evidence about the LABEL, routed to a human. The label below stays
    # HOLD as written pre-split, but ships flagged contested and excluded
    # from headline synthetic scores.
    ("data_quality_flag", a_data_quality_flag, (200, 800), True, "HOLD",
     "data_quality_flag", "a flag with nothing substantiating it... is a data-quality question, not a confirmed problem"),
    ("minor_anomaly_established", a_minor_anomaly_established, (500, 1400), True, "APPROVE",
     "weighing_proportionality", "a minor anomaly, or an immaterial amount, on an otherwise sound and well-established account does not warrant holding it"),
    ("fraud_linked", a_fraud_linked, (60, 400), True, "REJECT",
     "account_linkage", "a genuine connection to known fraud... is a serious concern"),
    ("incidental_overlap", a_incidental_overlap, (200, 900), True, "APPROVE",
     "account_linkage", "incidental overlaps that don't establish common control are not"),
    ("probe_then_scale", a_probe_then_scale, (15, 90), True, "REJECT",
     "transaction_activity", "systematic testing of payment credentials... are fraud"),
    # Adversarial-review probes (2026-08-24): each targets a seam the
    # external prompt review named. Labels follow the policy's own text.
    ("sanctions_partial_unresolved", a_sanctions_partial_unresolved, (300, 900), True, "HOLD",
     "sanctions_watchlist", "zero tolerance... a hit that does not hold up as the same individual is not, in itself, a concern"),
    ("prior_reject_precomputed_false", a_prior_reject_precomputed_false, (200, 700), True, "REJECT",
     "confirmed_history", "a confirmed, adjudicated problem against the same party is disqualifying"),
    ("payout_swap_established", a_payout_swap_established, (500, 1200), True, "HOLD",
     "identity_ownership", "where the party... cannot presently be established and money is exposed, the risk is unresolved"),
]


def generate(n_per: int) -> tuple[list[dict], dict[str, dict]]:
    cases, labels = [], {}
    idx = 0
    for name, builder, (t_lo, t_hi), verified, expected, clause, cite in ARCHETYPES:
        for _ in range(n_per):
            cid = f"CASE-{FIRST_ID + idx}"
            rng = random.Random(BASE_SEED + idx)
            opened = (date(2026, 7, 1) + timedelta(days=rng.randint(0, 45))).isoformat()
            chassis = _mk(rng, cid, rng.randint(t_lo, t_hi), verified, opened)
            case = builder(rng, chassis, opened)
            cases.append(case)
            labels[cid] = {"expected": expected, "kind": "synthetic",
                           "source": "construction", "archetype": name,
                           "policy_clause": clause, "policy_cite": cite}
            if name == "sanctions_partial_unresolved":
                labels[cid]["contested"] = True
                labels[cid]["contest_note"] = (
                    "fail-closed split: v5-era models REJECT (zero-tolerance "
                    "reading), written label says HOLD pending re-screening; "
                    "the reviewer-predicted fail-open APPROVE never occurred "
                    "in measurement. Verdict between two conservative "
                    "readings routed to the policy owner")
            if name == "data_quality_flag":
                labels[cid]["contested"] = True
                labels[cid]["contest_note"] = (
                    "policy underdetermines: HOLD (doubt + money exposed) vs "
                    "APPROVE (flag conflicts with record, established account, "
                    "CASE-115 precedent at small exposure); stable v1/v5 split "
                    "routed to human, excluded from headline synthetic score")
            idx += 1
    return cases, labels


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-archetype", type=int, default=4)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    cases, labels = generate(a.n_per_archetype)
    by_exp: dict[str, int] = {}
    for lab in labels.values():
        by_exp[lab["expected"]] = by_exp.get(lab["expected"], 0) + 1
    print(f"{len(cases)} synthetic cases across {len(ARCHETYPES)} archetypes: {by_exp}")
    if not a.write:
        print("dry run; pass --write to persist")
        return
    for case in cases:
        (CASES / f"{case['case_id'].lower()}.json").write_text(
            json.dumps(case, indent=2) + "\n")
    existing = json.loads(LABELS_PATH.read_text())
    existing.update(labels)
    LABELS_PATH.write_text(json.dumps(existing, indent=2) + "\n")
    print(f"wrote {len(cases)} case files, labels.json now {len(existing)} rows")


if __name__ == "__main__":
    main()
