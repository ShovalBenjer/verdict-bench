#!/usr/bin/env python3
"""Emit docs/assets/deck/key_numbers.json: every number the presentation
cites, each with the query that produced it, read fresh from the ledger and
benchmark.json at build time so the deck can never drift from the data."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "docs" / "assets" / "deck"
SUITE = "kind IN ('golden','perturbation')"
TEMP = "(temperature IS NULL OR temperature<=0.21)"


def main() -> None:
    DECK.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(ROOT / "state" / "verdict.sqlite3")
    bench = json.loads((ROOT / "ui" / "public" / "benchmark.json").read_text())

    def one(sql: str) -> tuple:
        row = db.execute(sql).fetchone()
        assert row is not None, sql
        return row

    total_runs, models, versions = one(
        "SELECT COUNT(*), COUNT(DISTINCT model_id), COUNT(DISTINCT prompt_version) FROM runs"
    )
    v5 = {}
    for m, n, ok in db.execute(
        f"""SELECT model_id, COUNT(*), SUM(correct) FROM runs JOIN cases USING(case_id)
            WHERE prompt_version='v5' AND {SUITE} AND {TEMP} GROUP BY model_id"""
    ):
        v5[m] = {"n": n, "correct": ok}
    inj = {}
    for pv, n, ok in db.execute(
        """SELECT prompt_version, COUNT(*), SUM(correct) FROM runs JOIN cases USING(case_id)
           WHERE kind='injection' AND model_id='gemini-flash'
           GROUP BY prompt_version ORDER BY prompt_version"""
    ):
        inj[pv] = {"n": n, "resisted": ok}
    hold = {}
    for pv, n, ok in db.execute(
        """SELECT prompt_version, COUNT(*), SUM(correct) FROM runs JOIN cases USING(case_id)
           WHERE kind='holdout' AND model_id='gemini-flash' GROUP BY prompt_version"""
    ):
        hold[pv] = {"n": n, "correct": ok}
    sc = bench.get("selfConsistency", [])
    out = {
        "provenance": "tools/deck_pack.py over state/verdict.sqlite3 + ui/public/benchmark.json",
        "generated_from_runs": total_runs,
        "models": models,
        "prompt_versions": versions,
        "total_cost_usd_list": bench.get("meta", {}).get("total_cost_usd_list"),
        "v5_suite_by_model": v5,
        "injection_resistance_flash": inj,
        "holdout_flash": hold,
        "self_consistency_cases": len(sc),
        "self_consistency_unanimous": sum(1 for r in sc if r.get("vote_fraction") == 1.0),
        "ladder_rungs": len(bench.get("ladder", [])),
        "trusted_cells": sum(
            1 for c in bench.get("cells", []) if c.get("trust") == "ok"
        ),
        "total_cells": len(bench.get("cells", [])),
    }
    (DECK / "key_numbers.json").write_text(json.dumps(out, indent=2))
    print(f"key_numbers.json: {total_runs} runs, {models} models, {versions} rungs")


if __name__ == "__main__":
    main()
