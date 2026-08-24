"""Minimum-viable profiling of the case corpus (dq.txt's four-rule MVM stack,
adapted from warehouse tables to case JSONs): completeness of load-bearing
fields, volume per kind and tier, label-file referential integrity, and
internal cross-reference consistency. Closes STATUS.md's named gap: the
inputs were read but never formally profiled.

Run: python3 tools/profile_cases.py   (exit 1 on any violation)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases"
LABELS = json.loads((ROOT / "data" / "labels.json").read_text())

REQUIRED_TOP = ("case_id", "flag_reason", "opened", "account", "money",
                "precomputed", "watchlist_hits", "device_login_history",
                "transactions", "linked_accounts", "prior_cases", "notes")
KNOWN_KINDS = {"golden", "perturbation", "metamorphic", "injection",
               "synthetic", "coverage", "holdout"}
KNOWN_SOURCES = {"expert", "adjudicated", "construction", "none"}


def main() -> int:
    violations: list[str] = []
    files = sorted(CASES.glob("*.json"))
    seen_ids: dict[str, str] = {}

    for f in files:
        try:
            case = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            violations.append(f"{f.name}: invalid JSON ({e})")
            continue
        cid = case.get("case_id")
        if not cid:
            violations.append(f"{f.name}: missing case_id")
            continue
        if cid in seen_ids:
            violations.append(f"{cid}: duplicate case_id ({f.name} and {seen_ids[cid]})")
        seen_ids[cid] = f.name
        # rule 1: completeness of load-bearing fields
        for k in REQUIRED_TOP:
            if k not in case:
                violations.append(f"{cid}: missing top-level field {k}")
        money = case.get("money", {})
        for k in ("on_hold_usd", "at_risk_usd", "lifetime_volume_usd"):
            if not isinstance(money.get(k), (int, float)):
                violations.append(f"{cid}: money.{k} missing or non-numeric")
        ver = case.get("account", {}).get("verification", {})
        if "status" not in ver:
            violations.append(f"{cid}: verification.status missing")
        # rule 4a: internal consistency: the confirmed-problem boolean must
        # agree with the prior-case record (POLICY's data-quality clause is
        # ABOUT this disagreement, so only flag when no label covers it)
        confirmed = case.get("precomputed", {}).get("confirmed_problem_on_record")
        prior_rejects = [p for p in case.get("prior_cases", [])
                         if p.get("decision") == "REJECT"]
        lab = LABELS.get(cid, {})
        if confirmed and not prior_rejects and lab.get("policy_clause") != "data_quality_flag":
            has_fraud_link = any(la.get("status") == "CLOSED_FRAUD"
                                 for la in case.get("linked_accounts", []))
            if not has_fraud_link:
                violations.append(
                    f"{cid}: confirmed_problem_on_record=true with no REJECT prior "
                    "case and no fraud-closed link (and not a data_quality_flag case)")

    # rule 3: referential integrity between labels.json and case files
    for cid, lab in LABELS.items():
        if cid not in seen_ids:
            violations.append(f"labels.json: {cid} has no case file")
        if lab.get("kind", "golden") not in KNOWN_KINDS:
            violations.append(f"labels.json: {cid} unknown kind {lab.get('kind')!r}")
        if lab.get("source", "none") not in KNOWN_SOURCES:
            violations.append(f"labels.json: {cid} unknown source {lab.get('source')!r}")
        if not lab.get("retired") and lab.get("expected") not in ("APPROVE", "HOLD", "REJECT", None):
            violations.append(f"labels.json: {cid} invalid expected {lab.get('expected')!r}")
    for cid in seen_ids:
        if cid not in LABELS:
            violations.append(f"{cid}: case file has no labels.json entry")

    # rule 2: volume per kind/tier, printed as the profile
    by_kind: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for cid in seen_ids:
        lab = LABELS.get(cid, {})
        by_kind[lab.get("kind", "golden")] = by_kind.get(lab.get("kind", "golden"), 0) + 1
        by_source[lab.get("source", "none")] = by_source.get(lab.get("source", "none"), 0) + 1
    print(f"{len(files)} case files, {len(LABELS)} label rows")
    print("by kind:  ", dict(sorted(by_kind.items())))
    print("by source:", dict(sorted(by_source.items())))

    if violations:
        print(f"\n{len(violations)} violation(s):")
        for v in violations:
            print("  " + v)
        return 1
    print("\nprofile clean: completeness, volume, referential integrity, consistency")
    return 0


if __name__ == "__main__":
    sys.exit(main())
