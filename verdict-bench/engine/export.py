"""Export the benchmark state to ui/public/benchmark.json for the UI."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from oec import cell_trust, wilson

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "state" / "verdict.sqlite3"
OUT = ROOT / "ui" / "public" / "benchmark.json"
# label tier per case (expert / adjudicated / constructed), emitted alongside
# the suite tag `kind` so the tiers SPEC.md forbids blending stay visible
LABELS: dict = json.loads((ROOT / "data" / "labels.json").read_text())

# assumption-stated cost matrix (SPEC.md business KPIs)
COST = {"FA": 2000.0, "FH": 45.0, "FR": 600.0}
PRICE = {  # $/MTok in, out; NVIDIA build free tier = 0
    "gemini-flash": (0.30, 2.50), "gemini-pro": (1.25, 10.0),
    "llama-3.3-70b": (0.0, 0.0), "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (1.0, 5.0),
    # ran on NVIDIA build free tier / DashScope free quota respectively;
    # list prices deliberately not encoded, cost_usd for these reads 0
    "nemotron-super-49b": (0.0, 0.0), "qwen3.8-max": (0.0, 0.0),
}

DECISION_SUITE_KINDS = ("golden", "perturbation")  # mirrors engine/oec.py


def error_cost(decision: str, expected: str) -> float:
    if decision == expected:
        return 0.0
    if expected == "REJECT":          # released or merely held a fraudster
        return COST["FA"] if decision == "APPROVE" else COST["FA"] * 0.25
    if expected == "APPROVE":         # friction on a good customer
        return COST["FR"] if decision == "REJECT" else COST["FH"]
    return COST["FH"] if decision == "APPROVE" else COST["FR"]  # expected HOLD


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cells: dict[tuple[str, str], dict] = {}
    runs = [dict(r) for r in con.execute(
        "SELECT r.*, c.expected, c.kind FROM runs r JOIN cases c USING(case_id)")]
    for r in runs:
        key = (r["prompt_version"], r["model_id"])
        cell = cells.setdefault(key, {"prompt": key[0], "model": key[1], "runs": []})
        cell["runs"].append(r)
    out_cells = []
    for (pv, mid), cell in sorted(cells.items()):
        rs = cell["runs"]
        # accuracy/EL/contract from FIRST run per case; repeats feed flip only
        first: dict[str, dict] = {}
        for r in rs:
            first.setdefault(r["case_id"], r)
        f = [r for r in first.values() if r["kind"] in DECISION_SUITE_KINDS]
        graded = [r for r in f if r["correct"] is not None]
        # robustness suites score separately, never blended into accuracy/EL
        inj = [r for r in first.values() if r["kind"] == "injection" and r["correct"] is not None]
        met = [r for r in first.values() if r["kind"] == "metamorphic" and r["correct"] is not None]
        # flip is a DECISION-SUITE metric, mirroring report(): robustness-case
        # repeats (e.g. the 102-INJ N=5 coin flip) measure injection
        # instability, which has its own columns; letting them into the cell
        # flip made export FLAG a cell the report ranked ok (caught 2026-08-24
        # the first time export computed trust).
        by_case: dict[str, list] = {}
        for r in rs:
            if r["decision"] and r["kind"] in DECISION_SUITE_KINDS:
                by_case.setdefault(r["case_id"], []).append(r["decision"])
        from collections import Counter
        flips = [1 - Counter(ds).most_common(1)[0][1] / len(ds)
                 for ds in by_case.values() if len(ds) > 1]
        lat = sorted(r["latency_ms"] for r in f if r["latency_ms"])
        el = sum(error_cost(r["decision"], r["expected"])
                 for r in graded if r["decision"]) / max(len(graded), 1) * 1000
        pin, pout = PRICE.get(mid, (0, 0))
        tok_cost = sum(((r["tokens_in"] or 0) * pin + (r["tokens_out"] or 0) * pout) / 1e6
                       for r in rs)
        # per-cell trust from the same implementation the report uses, so a
        # tile can police its own headline number (report suppresses the EL
        # figure on untrustworthy cells; the UI does the same client-side)
        k = sum(r["correct"] for r in graded)
        lo, hi = wilson(k, len(graded)) if graded else (None, None)
        mean_flip = (sum(flips) / len(flips)) if flips else None
        trust, violations, _ = cell_trust(con, pv, mid, lo, hi, mean_flip)
        out_cells.append({
            "prompt": pv, "model": mid, "n": len(rs),
            "trust": trust, "violations": violations,
            "accuracy": round(sum(r["correct"] for r in graded) / len(graded), 3) if graded else None,
            "flip": round(sum(flips) / len(flips), 2) if flips else None,
            "contract": round(sum(r["contract_ok"] for r in f) / len(f), 2) if f else None,
            "injection_resistance": (round(sum(r["correct"] for r in inj) / len(inj), 2)
                                     if inj else None),
            "invariance": (round(sum(r["correct"] for r in met) / len(met), 2)
                           if met else None),
            "p50_ms": lat[len(lat) // 2] if lat else None,
            "p95_ms": lat[min(len(lat) - 1, len(lat) * 95 // 100)] if lat else None,
            "expected_loss_per_1k": round(el),
            "cost_usd": round(tok_cost, 4),
            "errors": sum(1 for r in rs if r["error"]),
            "cases": [{
                "case_id": r["case_id"], "kind": r["kind"],
                "label_source": LABELS.get(r["case_id"], {}).get("source"),
                "expected": r["expected"], "repeat_idx": r["repeat_idx"],
                "decision": r["decision"], "correct": r["correct"],
                "contract_ok": r["contract_ok"], "latency_ms": r["latency_ms"],
                "reasoning": r["reasoning"], "error": r["error"],
            } for r in rs],
        })
    case_files = {}
    for row in con.execute("SELECT case_id, path, expected, kind FROM cases"):
        try:
            case_files[row["case_id"]] = {
                "json": json.loads(Path(row["path"]).read_text()),
                "expected": row["expected"], "kind": row["kind"],
                "label_source": LABELS.get(row["case_id"], {}).get("source")}
        except (OSError, json.JSONDecodeError) as e:
            case_files[row["case_id"]] = {"json": None, "error": str(e),
                                          "expected": row["expected"], "kind": row["kind"]}
    versions = {v: {"hypothesis": h} for v, h in con.execute(
        "SELECT version, hypothesis FROM prompts")}
    deltas = {"v1": "baseline: no policy", "v2": "+ policy verbatim",
              "v3": "procedure replaces quote", "v3c": "+ strict contract",
              "v4": "+ sanctions rule", "v4b": "+ worked proportionality example",
              "v4c": "+ card-testing counting scaffold",
              "v5": "+ loop-accepted edit"}
    for v, d in deltas.items():
        versions.setdefault(v, {})["delta"] = d
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"cells": out_cells, "caseFiles": case_files,
                               "versions": versions}, indent=1))
    print(f"wrote {OUT} with {len(out_cells)} cells / {len(runs)} runs")


if __name__ == "__main__":
    main()
