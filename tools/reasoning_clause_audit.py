#!/usr/bin/env python3
"""Which policy clause does the reasoning ACTUALLY cite? (Tanimura ch5
text-analysis pattern: quantitative categorization by keyword, not NLP.)

The rubric judge barely discriminates across rungs (3.9/4.0/3.2 flat), so
this measures attention directly: for every banked run with reasoning
text, keyword-match which POLICY.md clauses the text engages, then compare
against the case's tagged clause. Two numbers per cell: clause-hit rate
(does the reasoning engage the clause that decides the case) and
off-clause breadth (how many other clauses it wanders through).

Mechanical, deterministic, no LLM in the loop. Writes
state/clause_citation.json for the notebook. Run:
  python3 tools/reasoning_clause_audit.py
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Keyword families per clause: the policy's own vocabulary plus the case
# fields that instantiate it. Conservative on purpose: a hit means the
# reasoning engaged the concept, not that it quoted the policy.
CLAUSE_PATTERNS: dict[str, list[str]] = {
    "sanctions_watchlist": [r"sanction", r"watch\s*list", r"watchlist",
                            r"name[- ]?match", r"dob", r"false positive"],
    "account_linkage": [r"linked account", r"linkage", r"connection to",
                        r"common control", r"same (ssn|bank|owner)", r"closed[- ]fraud"],
    "transaction_activity": [r"card[- ]testing", r"credential", r"bust[- ]?out",
                             r"declin", r"extraction", r"payout", r"velocity",
                             r"build[- ]?up"],
    "identity_ownership": [r"identity", r"kyc", r"verif", r"cannot .{0,20}establish",
                           r"ownership", r"control of the account"],
    "confirmed_history": [r"prior (case|determination|issue)", r"adjudicat",
                          r"confirmed problem", r"chargeback fraud", r"prior_cases"],
    "weighing_proportionality": [r"proportion", r"exposure", r"track record",
                                 r"tenure", r"established", r"immaterial",
                                 r"benefit of the doubt", r"at[- ]risk", r"at stake"],
    "evidence_discipline": [r"own account of events", r"self[- ]report",
                            r"uncorroborat", r"not evidence"],
    "data_quality_flag": [r"data[- ]quality", r"unsubstantiated", r"legacy",
                          r"migrat", r"nothing substantiating", r"source record"],
}
COMPILED = {c: [re.compile(p, re.IGNORECASE) for p in pats]
            for c, pats in CLAUSE_PATTERNS.items()}


def clauses_cited(text: str) -> set[str]:
    return {c for c, pats in COMPILED.items() if any(p.search(text) for p in pats)}


def case_numbers(case_json: dict) -> set[str]:
    """Every numeric literal reachable in the case payload, normalized to
    canonical strings (2 decimal places stripped of trailing zeros), plus
    integer day/count forms, so a cited number can be matched structurally
    rather than by regex luck."""
    out: set[str] = set()

    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            canon = f"{float(v):.2f}".rstrip("0").rstrip(".")
            out.add(canon)
            out.add(f"{v:,.2f}".rstrip("0").rstrip("."))
        elif isinstance(v, str):
            for m in re.findall(r"\d[\d,]*\.?\d*", v):
                out.add(m.replace(",", ""))
    walk(case_json)
    return out


def grounded_rate(reasoning: str, case_json: dict) -> tuple[int, int]:
    """(grounded, cited): how many numbers the reasoning cites, and how many
    of those exist in the case payload (with derived-value tolerance: sums,
    percentages, and day-arithmetic are legitimate derivations, so anything
    unmatched only counts against grounding when it LOOKS like a case fact:
    a dollar amount or a day count)."""
    have = case_numbers(case_json)
    cited = re.findall(r"\$?([\d,]+\.?\d*)", reasoning)
    graded = 0
    grounded = 0
    for c in cited:
        raw = c.replace(",", "")
        if len(raw.rstrip(".0")) < 2:  # single digits: counts, list positions
            continue
        canon = raw
        try:
            canon = f"{float(raw):.2f}".rstrip("0").rstrip(".")
        except ValueError:
            continue
        graded += 1
        if canon in have or raw in have:
            grounded += 1
    return grounded, graded


def main() -> None:
    con = sqlite3.connect(ROOT / "state" / "verdict.sqlite3")
    rows = con.execute(
        """SELECT r.prompt_version, r.model_id, r.case_id, c.policy_clause, r.reasoning
           FROM runs r JOIN cases c USING(case_id)
           WHERE r.reasoning IS NOT NULL AND c.policy_clause IS NOT NULL
             AND c.kind IN ('golden','perturbation','synthetic')
             AND (r.temperature IS NULL OR r.temperature <= 0.21)""").fetchall()
    case_cache: dict[str, dict] = {}
    for (cid, path) in con.execute("SELECT case_id, path FROM cases"):
        try:
            case_cache[cid] = json.loads(Path(path).read_text())
        except (OSError, json.JSONDecodeError):
            pass
    cells: dict[str, dict] = {}
    for pv, mid, cid, tagged, reasoning in rows:
        cited = clauses_cited(reasoning)
        cell = cells.setdefault(f"{pv}|{mid}", {"n": 0, "hit": 0, "breadth": 0,
                                                "num_grounded": 0, "num_cited": 0})
        cell["n"] += 1
        cell["hit"] += int(tagged in cited)
        cell["breadth"] += len(cited)
        if cid in case_cache:
            g, c = grounded_rate(reasoning, case_cache[cid])
            cell["num_grounded"] += g
            cell["num_cited"] += c
    out = {k: {"n": v["n"], "clause_hit_rate": round(v["hit"] / v["n"], 3),
               "mean_breadth": round(v["breadth"] / v["n"], 2),
               "number_grounding_rate": (round(v["num_grounded"] / v["num_cited"], 3)
                                          if v["num_cited"] else None),
               "numbers_cited": v["num_cited"]}
           for k, v in sorted(cells.items()) if v["n"] >= 8}
    (ROOT / "state" / "clause_citation.json").write_text(json.dumps(out, indent=1))
    print(f"{len(rows)} reasoning rows audited across {len(out)} cells (n>=8)")
    for k, v in out.items():
        print(f"  {k:26s} hit {v['clause_hit_rate']:.0%}  breadth {v['mean_breadth']}")


if __name__ == "__main__":
    main()
