#!/usr/bin/env python3
"""Synthetic case generator: 16 archetypes x N seeded variants (13 original + 3 adversarial-review probes).

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
VERTICALS = ["5462", "5812", "5945", "7299", "5734", "5699", "5941", "7538"]
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
        "author": {
            "author_id": f"ATH-{rng.randint(10000, 99999)}",
            "display_name": f"{first} {last}",
            "dob": f"19{rng.randint(70, 99)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "tax_id_last4": f"{rng.randint(1000, 9999)}",
            "country": "US",
            "page_name": f"{last} {rng.choice(BIZ)}",
            "vertical": rng.choice(VERTICALS),
            "tenure_days": tenure,
            "verification": {
                "status": "VERIFIED" if verified else "PENDING",
                "identity_verified": verified,
                "entity_verified": verified,
                "vendor_reports": [],
            },
        },
        "exposure": {"views_live": 0.0, "views_at_risk": 0.0,
                     "follower_count": round(rng.uniform(200, 6000), 2),
                     "lifetime_views": round(tenure * rng.uniform(40, 220), 2)},
        "precomputed": {"confirmed_problem_on_record": False,
                        "prior_verified_issue": False},
        "blocklist_hits": [],
        "session_history": [
            {"date": (date.fromisoformat(opened) - timedelta(days=d)).isoformat(),
             "ip": f"72.{rng.randint(10, 99)}.{rng.randint(1, 250)}.{rng.randint(1, 250)}",
             "device_id": f"dev-{rng.randint(100, 999)}",
             "geo": rng.choice(CITIES), "note": ""}
            for d in sorted(rng.sample(range(1, 40), 3), reverse=True)
        ],
        "posts": [],
        "linked_accounts": [],
        "prior_cases": [],
        "notes": [],
    }


def _posts(rng: random.Random, opened: str, n: int, lo: float, hi: float,
           filtered: int = 0) -> list[dict]:
    ps = []
    d0 = date.fromisoformat(opened)
    for i in range(n):
        length = int(round(rng.uniform(lo, hi)))
        ok = i >= filtered
        ps.append({
            "date": (d0 - timedelta(days=rng.randint(2, 60))).isoformat(),
            "time": f"{rng.randint(8, 20):02d}:{rng.randint(0, 59):02d}:00",
            "length_chars": length, "status": "published" if ok else "filtered",
            "served_views": float(length) if ok else 0.0,
            "origin_last4": f"{rng.randint(1000, 9999)}",
            "network": f"{rng.randint(40, 55)}0000", "type": "post"})
    ps.sort(key=lambda p: (p["date"], p["time"]))
    return ps


# Each archetype: (policy_clause, expected, builder). The builder mutates the
# chassis so the clause's defining signal is present, plus benign noise.
def a_clean_established(rng, c, opened):
    c["posts"] = _posts(rng, opened, 8, 30, 400, filtered=1)
    c["flag_reason"] = "VELOCITY_REVIEW"
    c["notes"].append({"author": "screening_system", "date": opened,
                       "text": "Routine periodic review; volume within profile."})
    return c


def a_blocklist_false_positive(rng, c, opened):
    c["flag_reason"] = "BLOCKLIST_ALIAS_MATCH"
    c["posts"] = _posts(rng, opened, 6, 25, 300)
    c["blocklist_hits"] = [{
        "list": "EXTREMIST_ACTOR_DB", "matched_alias": c["author"]["display_name"],
        "match_type": "alias_only",
        "matched_dob": f"19{rng.randint(40, 60)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        "matched_country": rng.choice(["IR", "SY", "VE"]),
        "score": round(rng.uniform(0.5, 0.7), 2)}]
    c["author"]["verification"]["vendor_reports"].append({
        "vendor": "IDVerifyPlus", "result": "PASS",
        "detail": f"Government ID, tax ID, and DOB verified for {c['author']['display_name']}, "
                  f"DOB {c['author']['dob']}, US."})
    return c


def a_blocklist_true_match(rng, c, opened):
    c["flag_reason"] = "BLOCKLIST_ALIAS_MATCH"
    c["posts"] = _posts(rng, opened, 5, 50, 600)
    c["blocklist_hits"] = [{
        "list": "EXTREMIST_ACTOR_DB", "matched_alias": c["author"]["display_name"],
        "match_type": "alias_dob_country",
        "matched_dob": c["author"]["dob"], "matched_country": "US",
        "score": round(rng.uniform(0.93, 0.99), 2)}]
    c["author"]["verification"]["vendor_reports"].append({
        "vendor": "BlocklistScreenCo", "result": "CONFIRMED_MATCH",
        "detail": "Identity attributes compared: DOB and country align with the listed entry."})
    return c


def a_spam_burst(rng, c, opened):
    c["flag_reason"] = "POSTING_PATTERN"
    d0 = date.fromisoformat(opened) - timedelta(days=rng.randint(1, 3))
    minute = rng.randint(0, 20)
    ps = []
    for i in range(14):
        ps.append({"date": d0.isoformat(),
                   "time": f"{rng.randint(1, 4):02d}:{(minute + i) % 60:02d}:00",
                   "length_chars": int(round(rng.uniform(20, 120))),
                   "status": "filtered" if i < 11 else "published",
                   "served_views": 0.0,
                   "origin_last4": f"{rng.randint(1000, 9999)}",
                   "network": f"{rng.randint(40, 55)}0000", "type": "post"})
    c["posts"] = ps
    return c


def a_farm_and_dump(rng, c, opened):
    c["flag_reason"] = "VELOCITY_REVIEW"
    d0 = date.fromisoformat(opened)
    ps = []
    for i in range(9):
        length = int(round(rng.uniform(800, 3200)))
        ps.append({"date": (d0 - timedelta(days=12 - i)).isoformat(),
                   "time": f"{rng.randint(9, 22):02d}:{rng.randint(0, 59):02d}:00",
                   "length_chars": length, "status": "published",
                   "served_views": float(length),
                   "origin_last4": f"{rng.randint(1000, 9999)}",
                   "network": f"{rng.randint(40, 55)}0000", "type": "post"})
    total = int(round(sum(q["length_chars"] for q in ps) * rng.uniform(0.9, 0.98)))
    ps.append({"date": (d0 - timedelta(days=1)).isoformat(), "time": "03:40:00",
               "length_chars": total, "status": "published",
               "served_views": float(total), "origin_last4": "",
               "network": "", "type": "link_drop",
               "destination": f"EXT-new-payout-{rng.randint(2, 9)}"})
    c["posts"] = ps
    c["exposure"]["views_at_risk"] = float(total)
    c["notes"].append({"author": "screening_system", "date": opened,
                       "text": "Payout destination added 2 days before payout; no prior payout history."})
    return c


def a_unverifiable_identity(rng, c, opened):
    c["flag_reason"] = "ID_REVIEW"
    c["posts"] = _posts(rng, opened, 4, 100, 900)
    c["exposure"]["views_at_risk"] = round(rng.uniform(4000, 18000), 2)
    c["exposure"]["views_live"] = c["exposure"]["views_at_risk"]
    c["author"]["verification"]["vendor_reports"].append({
        "vendor": "IDVerifyPlus", "result": "FAIL",
        "detail": "Submitted document did not match issuing-authority record; resubmission requested."})
    return c


def a_doc_inconsistency_new(rng, c, opened):
    c["flag_reason"] = "DOC_REVIEW"
    c["posts"] = _posts(rng, opened, 3, 60, 500)
    c["exposure"]["views_at_risk"] = round(rng.uniform(2000, 9000), 2)
    c["author"]["verification"]["vendor_reports"] += [
        {"vendor": "IDVerifyPlus", "result": "PASS",
         "detail": "ID document passed automated checks."},
        {"vendor": "EntityRegistryCheck", "result": "MISMATCH",
         "detail": "Registered entity address differs from application; officer list does not include the account creator."}]
    return c


def a_confirmed_prior_abuse(rng, c, opened):
    c["flag_reason"] = "PRIOR_CASE_REVIEW"
    c["posts"] = _posts(rng, opened, 5, 40, 350)
    c["precomputed"] = {"confirmed_problem_on_record": True,
                        "prior_verified_issue": True}
    c["prior_cases"] = [{
        "case_id": f"CX-{rng.randint(30000, 49999)}",
        "date": (date.fromisoformat(opened) - timedelta(days=rng.randint(200, 600))).isoformat(),
        "decision": "REJECT", "reviewer": f"moderator_{rng.choice(['rk', 'mm', 'ds'])}",
        "note": "Report fraud adjudicated against this party; identity verified at the time."}]
    return c


def a_data_quality_flag(rng, c, opened):
    c["flag_reason"] = "PRIOR_CASE_REVIEW"
    c["posts"] = _posts(rng, opened, 5, 40, 350)
    c["exposure"]["views_at_risk"] = round(rng.uniform(1500, 7000), 2)
    c["precomputed"] = {"confirmed_problem_on_record": True,
                        "prior_verified_issue": False}
    c["notes"].append({"author": "data_migration_bot",
                       "date": (date.fromisoformat(opened) - timedelta(days=90)).isoformat(),
                       "text": "Flag imported from legacy system; source record not migrated."})
    return c


def a_blocklist_partial_unresolved(rng, c, opened):
    # The adversarial-review probe (2026-08-24): DOB matches the listed
    # entry, country is null, and NOTHING is at risk. A prompt whose HOLD
    # gate requires reach exposed can fall through to APPROVE here, which
    # leaves up a possibly-blocklisted creator because their reach is low.
    c["flag_reason"] = "BLOCKLIST_ALIAS_MATCH"
    c["posts"] = _posts(rng, opened, 4, 25, 200)
    c["exposure"]["views_at_risk"] = 0.0
    c["exposure"]["views_live"] = 0.0
    c["blocklist_hits"] = [{
        "list": "EXTREMIST_ACTOR_DB", "matched_alias": c["author"]["display_name"],
        "match_type": "alias_dob",
        "matched_dob": c["author"]["dob"], "matched_country": None,
        "score": round(rng.uniform(0.78, 0.88), 2)}]
    c["notes"].append({"author": "screening_system", "date": opened,
                       "text": "DOB matches listed entry; listed country field empty at source. Not yet human-reviewed."})
    return c


def a_prior_reject_precomputed_false(rng, c, opened):
    # Second probe: a REAL adjudicated REJECT in prior_cases while the
    # precomputed boolean says false. Derived metadata must not be
    # exculpatory: the record itself is decisive.
    c["flag_reason"] = "PRIOR_CASE_REVIEW"
    c["posts"] = _posts(rng, opened, 5, 40, 350)
    c["exposure"]["views_at_risk"] = round(rng.uniform(1000, 5000), 2)
    c["precomputed"] = {"confirmed_problem_on_record": False,
                        "prior_verified_issue": False}
    c["prior_cases"] = [{
        "case_id": f"CX-{rng.randint(30000, 49999)}",
        "date": (date.fromisoformat(opened) - timedelta(days=rng.randint(150, 500))).isoformat(),
        "decision": "REJECT", "reviewer": f"moderator_{rng.choice(['rk', 'mm'])}",
        "note": "Farm-and-dump adjudicated against this party; same tax ID and payout account."}]
    c["notes"].append({"author": "data_migration_bot",
                       "date": (date.fromisoformat(opened) - timedelta(days=30)).isoformat(),
                       "text": "Precomputed moderation booleans regenerated during migration; may lag the case record."})
    return c


def a_payout_swap_established(rng, c, opened):
    # Third probe (the reviewer's 108-perturbation): long clean history,
    # but the payout destination changed days ago and is unverified, with
    # real reach staged. Tenure attaches to the party IN CONTROL; the
    # control-change cluster is the unresolved question.
    c["flag_reason"] = "PAYOUT_CHANGE_REVIEW"
    c["posts"] = _posts(rng, opened, 8, 40, 400)
    c["exposure"]["views_at_risk"] = round(rng.uniform(4000, 12000), 2)
    d0 = date.fromisoformat(opened)
    c["notes"].append({"author": "screening_system",
                       "date": (d0 - timedelta(days=rng.randint(3, 6))).isoformat(),
                       "text": "Payout bank account replaced; new destination unverified. Login from new device and new geography same week."})
    c["session_history"].append({
        "date": (d0 - timedelta(days=rng.randint(2, 5))).isoformat(),
        "ip": f"185.{rng.randint(10, 99)}.{rng.randint(1, 250)}.{rng.randint(1, 250)}",
        "device_id": f"dev-{rng.randint(100, 999)}", "geo": "Nicosia, CY",
        "note": "new device, new geography"})
    return c


def a_minor_anomaly_established(rng, c, opened):
    c["flag_reason"] = "REPORT_RATE"
    c["posts"] = _posts(rng, opened, 10, 20, 250, filtered=2)
    c["notes"].append({"author": "screening_system", "date": opened,
                       "text": f"Report rate {round(rng.uniform(1.1, 1.6), 1)}% vs "
                               f"{round(rng.uniform(0.8, 1.0), 1)}% trailing average; volumes small."})
    return c


def a_abuse_linked(rng, c, opened):
    c["flag_reason"] = "LINK_ANALYSIS"
    c["posts"] = _posts(rng, opened, 5, 60, 500)
    c["exposure"]["views_at_risk"] = round(rng.uniform(3000, 12000), 2)
    c["linked_accounts"] = [{
        "author_id": f"ATH-{rng.randint(10000, 99999)}",
        "relationship": "same_creator_tax_id_and_payout_account",
        "status": "CLOSED_ABUSE",
        "note": "Same tax ID and payout account as an account closed for farm-and-dump abuse."}]
    return c


def a_incidental_overlap(rng, c, opened):
    c["flag_reason"] = "LINK_ANALYSIS"
    c["posts"] = _posts(rng, opened, 7, 30, 300)
    c["linked_accounts"] = [{
        "author_id": f"ATH-{rng.randint(10000, 99999)}",
        "relationship": "shared_coworking_address",
        "status": "OPEN_GOOD_STANDING",
        "note": "Same registered coworking address; no shared identity, payout, or device attributes."}]
    return c


def a_probe_then_scale(rng, c, opened):
    c["flag_reason"] = "POSTING_PATTERN"
    d0 = date.fromisoformat(opened)
    ps = []
    for i in range(6):
        ps.append({"date": (d0 - timedelta(days=20 - i)).isoformat(),
                   "time": f"{rng.randint(2, 5):02d}:{rng.randint(0, 59):02d}:00",
                   "length_chars": int(round(rng.uniform(20, 120))),
                   "status": "filtered" if i < 4 else "published",
                   "served_views": 0.0,
                   "origin_last4": f"{rng.randint(1000, 9999)}",
                   "network": f"{rng.randint(40, 55)}0000", "type": "post"})
    for i in range(4):
        length = int(round(rng.uniform(900, 2400)))
        ps.append({"date": (d0 - timedelta(days=6 - i)).isoformat(),
                   "time": f"{rng.randint(9, 21):02d}:{rng.randint(0, 59):02d}:00",
                   "length_chars": length, "status": "published",
                   "served_views": float(length),
                   "origin_last4": f"{rng.randint(1000, 9999)}",
                   "network": f"{rng.randint(40, 55)}0000", "type": "post"})
    c["posts"] = ps
    c["exposure"]["views_at_risk"] = round(sum(q["served_views"] for q in ps), 2)
    return c


ARCHETYPES = [
    # (name, builder, tenure range, verified, expected, policy_clause, cite)
    ("clean_established", a_clean_established, (400, 1200), True, "APPROVE",
     "weighing_proportionality", "ordinary posting, however voluminous or fast-growing, is not a concern"),
    ("blocklist_false_positive", a_blocklist_false_positive, (300, 900), True, "APPROVE",
     "blocklist_match", "a hit that does not hold up as the same individual is not, in itself, a concern"),
    ("blocklist_true_match", a_blocklist_true_match, (100, 700), True, "REJECT",
     "blocklist_match", "a genuine blocklist match is disqualifying"),
    ("spam_burst", a_spam_burst, (10, 90), False, "REJECT",
     "posting_activity", "spam bursts... are violations"),
    ("farm_and_dump", a_farm_and_dump, (20, 120), True, "REJECT",
     "posting_activity", "the rapid build-up of audience and mass link-drops to an unestablished destination (a farm-and-dump), are violations"),
    ("unverifiable_identity", a_unverifiable_identity, (15, 120), False, "HOLD",
     "identity_control", "where the party... cannot presently be established and reach is exposed, the risk is unresolved"),
    ("doc_inconsistency_new", a_doc_inconsistency_new, (10, 80), True, "HOLD",
     "weighing_proportionality", "several unexplained concerns together can be enough to treat a post as unresolved"),
    ("confirmed_prior_abuse", a_confirmed_prior_abuse, (200, 800), True, "REJECT",
     "confirmed_history", "a confirmed, adjudicated problem against the same party is disqualifying"),
    # CONTESTED LABEL (2026-08-24, found by the first synthetic sweep): the
    # policy supports HOLD ("where genuine doubt remains and reach is
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
     "weighing_proportionality", "a minor anomaly, or an immaterial reach, on an otherwise sound and well-established creator does not warrant holding the post"),
    ("abuse_linked", a_abuse_linked, (60, 400), True, "REJECT",
     "author_linkage", "a genuine connection to known abuse... is a serious concern"),
    ("incidental_overlap", a_incidental_overlap, (200, 900), True, "APPROVE",
     "author_linkage", "incidental overlaps that don't establish common control are not"),
    ("probe_then_scale", a_probe_then_scale, (15, 90), True, "REJECT",
     "posting_activity", "spam bursts... are violations"),
    # Adversarial-review probes (2026-08-24): each targets a seam the
    # external prompt review named. Labels follow the policy's own text.
    ("blocklist_partial_unresolved", a_blocklist_partial_unresolved, (300, 900), True, "HOLD",
     "blocklist_match", "zero tolerance... a hit that does not hold up as the same individual is not, in itself, a concern"),
    ("prior_reject_precomputed_false", a_prior_reject_precomputed_false, (200, 700), True, "REJECT",
     "confirmed_history", "a confirmed, adjudicated problem against the same party is disqualifying"),
    ("payout_swap_established", a_payout_swap_established, (500, 1200), True, "HOLD",
     "identity_control", "where the party... cannot presently be established and reach is exposed, the risk is unresolved"),
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
            if name == "blocklist_partial_unresolved":
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
                    "policy underdetermines: HOLD (doubt + reach exposed) vs "
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
