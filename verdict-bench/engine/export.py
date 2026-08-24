"""Export the benchmark state to ui/public/benchmark.json for the UI."""
from __future__ import annotations

import difflib
import json
import random
import re
import sqlite3
from pathlib import Path

from oec import DECISION_SUITE_KINDS, cell_trust, coverage_report, flip_rates, wilson

# the ladder's parent chain, for per-rung diffs in the UI's prompt view
PARENT = {"v2": "v1", "v3": "v2", "v3c": "v3", "v4": "v3c",
          "v4b": "v4", "v4c": "v4b", "v5": "v4c",
          "v6": "v5", "v6b": "v5"}

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "state" / "verdict.sqlite3"
OUT = ROOT / "ui" / "public" / "benchmark.json"
# label tier per case (expert / adjudicated / constructed), emitted alongside
# the suite tag `kind` so the tiers SPEC.md forbids blending stay visible
LABELS: dict = json.loads((ROOT / "data" / "labels.json").read_text())

# assumption-stated cost matrix (SPEC.md business KPIs)
COST = {"FA": 2000.0, "FH": 45.0, "FR": 600.0}
# ONE more named assumption (queue burden): analyst cost per HOLD review.
# Not in SPEC; stated here and everywhere the number renders.
REVIEW_COST_USD = 35.0
# mechanical citation-fidelity vocabulary: case-field concepts the README's
# own contract expects reasoning to cite ("with its reasoning, citing the
# case"); >=3 concepts AND >=2 literal numbers = a citing reasoning.
CITE_FIELDS = ("tenure", "at_risk", "on_hold", "verification", "watchlist",
               "instrument", "declin", "prior", "linked", "kyc", "kyb",
               "settled", "payout", "balance", "lifetime")
PRICE = {  # $/MTok in, out; NVIDIA build free tier = 0
    "gemini-flash": (0.30, 2.50), "gemini-pro": (1.25, 10.0),
    "llama-3.3-70b": (0.0, 0.0), "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (1.0, 5.0),
    # ran on NVIDIA build free tier / DashScope free quota respectively;
    # list prices deliberately not encoded, cost_usd for these reads 0
    "nemotron-super-49b": (0.0, 0.0), "qwen3.8-max": (0.0, 0.0),
}



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
    # at-risk dollars per case, for the dollar-weighted detection KPI
    at_risk: dict[str, float] = {}
    for row in con.execute("SELECT case_id, path FROM cases"):
        try:
            at_risk[row["case_id"]] = float(json.loads(Path(row["path"]).read_text())
                                            .get("money", {}).get("at_risk_usd", 0.0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            at_risk[row["case_id"]] = 0.0
    cells: dict[tuple[str, str], dict] = {}
    runs = [dict(r) for r in con.execute(
        "SELECT r.*, c.expected, c.kind FROM runs r JOIN cases c USING(case_id) "
        "WHERE r.temperature IS NULL OR r.temperature <= 0.21")]
    # self-consistency samples (temp-raised repeats of the champion): the vote
    # fraction over N samples is the uncertainty signal verbalized confidence
    # failed to be; exported per case for the calibration surface
    sc_rows = con.execute(
        "SELECT r.case_id, r.decision, c.expected FROM runs r JOIN cases c USING(case_id) "
        "WHERE r.temperature > 0.5 AND r.prompt_version='v5' AND r.model_id='gemini-flash' "
        "AND r.decision IS NOT NULL AND c.kind IN ('golden','perturbation')").fetchall()
    sc_by_case: dict[str, dict] = {}
    for cid, dec, exp in sc_rows:
        e = sc_by_case.setdefault(cid, {"votes": {}, "expected": exp})
        e["votes"][dec] = e["votes"].get(dec, 0) + 1
    self_consistency = []
    for cid, e in sorted(sc_by_case.items()):
        total = sum(e["votes"].values())
        modal = max(e["votes"], key=lambda d: e["votes"][d])
        self_consistency.append({
            "case_id": cid, "n": total, "votes": e["votes"], "modal": modal,
            "vote_fraction": round(e["votes"][modal] / total, 2),
            "modal_correct": int(modal == e["expected"]),
        })
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
        flips = flip_rates(by_case)
        lat = sorted(r["latency_ms"] for r in f if r["latency_ms"])

        # EL must mirror oec.expected_loss EXACTLY, including the unparseable
        # branch: a row with no recoverable decision is charged the worst cost
        # reachable from its expected label and KEPT in the denominator.
        # Before 2026-08-24 export dropped those rows (correct IS NULL), so
        # the UI tile could show $0 where the terminal report charged
        # worst-case for the same cell; the differential test now pins them.
        def cost_of(r: dict) -> float:
            if r["decision"] in ("APPROVE", "HOLD", "REJECT"):
                return error_cost(r["decision"], r["expected"])
            return max(error_cost(d, r["expected"])
                       for d in ("APPROVE", "HOLD", "REJECT"))
        el_rows = [r for r in f if r["expected"]]
        el = sum(cost_of(r) for r in el_rows) / max(len(el_rows), 1) * 1000
        # case-clustered bootstrap on the weighted loss (Spiegelhalter Type A:
        # sampling variability only; the cost figures themselves are Type B
        # assumptions and carry no interval, said wherever the number shows).
        # Resample unit is the CASE, never the run: repeats are correlated.
        el_ci = None
        if el_rows:
            rng = random.Random(1789)  # fixed seed: exports are reproducible
            costs = [cost_of(r) for r in el_rows]
            if costs:
                boots = sorted(
                    sum(rng.choice(costs) for _ in costs) / len(costs) * 1000
                    for _ in range(1000))
                el_ci = [round(boots[25]), round(boots[974])]
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
        # 3x3 confusion matrix (expected x decided) over decision-suite first
        # runs; None decisions (contract failures) counted in their own row
        confusion: dict[str, dict[str, int]] = {}
        for r in graded:
            dec = r["decision"] or "NONE"
            confusion.setdefault(r["expected"], {}).setdefault(dec, 0)
            confusion[r["expected"]][dec] += 1
        # cross-family rubric means for this cell, by judge (r1 rubric)
        rubric = {}
        for jm, n_j, fid, evi, pro in con.execute(
                "SELECT j.judge_model, COUNT(*), AVG(j.fidelity), AVG(j.evidence), "
                "AVG(j.proportionality) FROM judgments j JOIN runs r USING(run_id) "
                "WHERE r.prompt_version=? AND r.model_id=? AND j.fidelity IS NOT NULL "
                "GROUP BY j.judge_model", (pv, mid)):
            rubric[jm] = {"n": n_j, "fidelity": round(fid, 1),
                          "evidence": round(evi, 1), "proportionality": round(pro, 1)}
        # SPEC business KPIs, per cell, from suite first runs. Also the two
        # payments-industry framings the suite CAN support (2026-08-24):
        # insult rate (good customers declined per the industry's own word)
        # and dollar-weighted detection (fraud $ caught over fraud $ present).
        # bps-of-processed-volume and chargeback-threshold positioning need
        # volume assumptions the suite does not carry; absent by name.
        approve_graded = [r for r in graded if r["expected"] == "APPROVE"]
        insult_rate = (sum(1 for r in approve_graded if r["decision"] == "REJECT")
                       / len(approve_graded)) if approve_graded else None
        rej_graded = [r for r in graded if r["expected"] == "REJECT"]
        rej_dollars = sum(at_risk.get(r["case_id"], 0.0) for r in rej_graded)
        caught = sum(at_risk.get(r["case_id"], 0.0) for r in rej_graded
                     if r["decision"] == "REJECT")
        value_detection = round(caught / rej_dollars, 3) if rej_dollars else None
        hold_rate = (sum(1 for r in graded if r["decision"] == "HOLD") / len(graded)) if graded else None
        cost_per_case = round(tok_cost / len(graded), 4) if graded else None
        # auto-decision rate (SPEC: stable N-run agreement AND confidence >= 0.8);
        # honest n/a when a cell has no repeated cases to measure stability on
        # SPEC deviation, deliberate and documented (WRITEUP "A SPEC
        # deviation, self-reported"): SPEC gates auto-decision on stated
        # confidence >= 0.8, but v5conf showed verbalized confidence is
        # decorative (95-100% on everything, including misses), so gating a
        # business KPI on it would contradict this repo's own finding. The
        # shipped definition is repeat stability alone.
        rep_cases = {cid: ds for cid, ds in by_case.items() if len(ds) > 1}
        auto = None
        if rep_cases:
            stable = [cid for cid, ds in rep_cases.items() if len(set(ds)) == 1]
            auto = round(len(stable) / len(rep_cases), 2)
        # citation fidelity (README: reasoning that CITES the case), mechanical
        reasons = [r["reasoning"] for r in first.values() if r["reasoning"]]
        cite_ok = sum(1 for rx in reasons
                      if sum(1 for fld in CITE_FIELDS if re.search(fld, rx, re.IGNORECASE)) >= 3
                      and len(re.findall(r"\$?\d[\d,]*\.?\d*", rx)) >= 2)
        citation_fidelity = round(cite_ok / len(reasons), 2) if reasons else None
        # exposure bands over ALL graded first runs, contested excluded: the
        # mid-band is where models measurably fail (69% vs 88% at the edges)
        bands: dict[str, list[int]] = {"$0": [0, 0], "<$1k": [0, 0],
                                       "$1k-10k": [0, 0], ">$10k": [0, 0]}
        for r in first.values():
            if r["correct"] is None or LABELS.get(r["case_id"], {}).get("contested"):
                continue
            ar = at_risk.get(r["case_id"], 0.0)
            band = ("$0" if ar == 0 else "<$1k" if ar < 1000
                    else "$1k-10k" if ar < 10000 else ">$10k")
            bands[band][1] += 1
            bands[band][0] += r["correct"]
        exposure_bands = {b: {"correct": k, "n": n} for b, (k, n) in bands.items() if n}
        # generalization: same prompt, three evidence tiers, one glance
        def tier_acc(kinds: tuple, first=first) -> float | None:  # bind the loop var (B023)
            g = [r for r in first.values() if r["kind"] in kinds
                 and r["correct"] is not None
                 and not LABELS.get(r["case_id"], {}).get("contested")]
            return round(sum(r["correct"] for r in g) / len(g), 3) if g else None
        generalization = {"suite": tier_acc(("golden", "perturbation")),
                          "holdout": tier_acc(("holdout",)),
                          "synthetic": tier_acc(("synthetic",))}
        out_cells.append({
            "prompt": pv, "model": mid, "n": len(rs),
            "trust": trust, "violations": violations,
            "hold_rate": hold_rate, "cost_per_case": cost_per_case,
            "citation_fidelity": citation_fidelity,
            "exposure_bands": exposure_bands,
            "generalization": generalization,
            "queue_cost_per_1k": (round(hold_rate * 1000 * REVIEW_COST_USD)
                                   if hold_rate is not None else None),
            "throughput_per_hour": (round(3600000 / lat[len(lat) // 2])
                                     if lat else None),
            "auto_decision_rate": auto, "insult_rate": insult_rate,
            "value_detection_rate": value_detection,
            "confusion": confusion, "rubric": rubric,
            "accuracy": round(sum(r["correct"] for r in graded) / len(graded), 3) if graded else None,
            "flip": round(sum(flips) / len(flips), 2) if flips else None,
            "contract": round(sum(r["contract_ok"] for r in f) / len(f), 2) if f else None,
            "injection_resistance": (round(sum(r["correct"] for r in inj) / len(inj), 2)
                                     if inj else None),
            "invariance": (round(sum(r["correct"] for r in met) / len(met), 2)
                           if met else None),
            "p50_ms": lat[len(lat) // 2] if lat else None,
            "p95_ms": lat[min(len(lat) - 1, len(lat) * 95 // 100)] if lat else None,
            "expected_loss_per_1k": round(el), "el_ci": el_ci,
            "cost_usd": round(tok_cost, 4),
            "errors": sum(1 for r in rs if r["error"]),
            "cases": [{
                "case_id": r["case_id"], "kind": r["kind"],
                "label_source": LABELS.get(r["case_id"], {}).get("source"),
                "expected": r["expected"], "repeat_idx": r["repeat_idx"],
                "decision": r["decision"], "correct": r["correct"],
                "confidence": r["confidence"],
                "contract_ok": r["contract_ok"], "latency_ms": r["latency_ms"],
                "reasoning": r["reasoning"], "error": r["error"],
            } for r in rs],
        })
    case_files = {}
    for row in con.execute("SELECT case_id, path, expected, kind, policy_clause, retired FROM cases"):
        lab = LABELS.get(row["case_id"], {})
        try:
            case_files[row["case_id"]] = {
                "json": json.loads(Path(row["path"]).read_text()),
                "expected": row["expected"], "kind": row["kind"],
                "policy_clause": row["policy_clause"],
                "policy_cite": lab.get("policy_cite"),
                "retired": bool(row["retired"]),
                "label_source": lab.get("source"),
                "archetype": lab.get("archetype"),
                "contested": bool(lab.get("contested")),
                "contest_note": lab.get("contest_note")}
        except (OSError, json.JSONDecodeError) as e:
            case_files[row["case_id"]] = {"json": None, "error": str(e),
                                          "expected": row["expected"], "kind": row["kind"]}
    # policy-clause coverage board (the find-then-close story of beat 1)
    coverage = [{"clause": c.clause, "cite": c.policy_cite, "case_ids": c.case_ids,
                 "n_cases": c.n_cases} for c in coverage_report(con)]
    # calibration raw points: stated confidence vs correctness, decision-suite
    # first runs (repeat_idx by first-seen per cell handled client-side is
    # wrong; use MIN(run_id) per (cell, case) here). SPEC lists calibration
    # error as a KPI; the confidence column existed since day one, unused.
    calibration = [
        {"model": m, "prompt": p, "confidence": conf, "correct": corr}
        for m, p, conf, corr in con.execute(
            """SELECT r.model_id, r.prompt_version, r.confidence, r.correct
               FROM runs r JOIN cases c USING(case_id)
               WHERE c.kind IN ('golden','perturbation') AND r.confidence IS NOT NULL
                 AND r.correct IS NOT NULL
                 AND r.run_id IN (SELECT MIN(r2.run_id) FROM runs r2
                                  WHERE r2.case_id=r.case_id
                                    AND r2.prompt_version=r.prompt_version
                                    AND r2.model_id=r.model_id)""")]
    # clause x model miss table (SPEC: clause tags exist for slicing; this is
    # the first surface that actually slices on them)
    clause_misses = [
        {"model": m, "clause": cl, "n": n, "miss": miss}
        for m, cl, n, miss in con.execute(
            """SELECT r.model_id, c.policy_clause, COUNT(*),
                      SUM(CASE WHEN r.correct=0 THEN 1 ELSE 0 END)
               FROM runs r JOIN cases c USING(case_id)
               WHERE c.kind IN ('golden','perturbation') AND c.policy_clause IS NOT NULL
                 AND r.correct IS NOT NULL
                 AND r.run_id IN (SELECT MIN(r2.run_id) FROM runs r2
                                  WHERE r2.case_id=r.case_id
                                    AND r2.prompt_version=r.prompt_version
                                    AND r2.model_id=r.model_id)
               GROUP BY r.model_id, c.policy_clause""")]
    # prompt texts + per-rung unified diffs, so the ladder is inspectable in
    # the UI (the prompt IS the assignment's deliverable)
    prompts_dir = ROOT / "engine" / "prompts"
    texts = {p.stem: p.read_text() for p in sorted(prompts_dir.glob("v*.md"))}
    ladder = {}
    for v, text in texts.items():
        parent = PARENT.get(v)
        diff = None
        if parent and parent in texts:
            diff = "\n".join(difflib.unified_diff(
                texts[parent].splitlines(), text.splitlines(),
                fromfile=parent, tofile=v, lineterm="", n=2))
        ladder[v] = {"text": text, "parent": parent, "diff_vs_parent": diff}
    versions = {v: {"hypothesis": h} for v, h in con.execute(
        "SELECT version, hypothesis FROM prompts")}
    deltas = {"v1": "baseline: no policy", "v2": "+ policy verbatim",
              "v3": "procedure replaces quote", "v3c": "+ strict contract",
              "v4": "+ sanctions rule", "v4b": "+ worked proportionality example",
              "v4c": "+ card-testing counting scaffold",
              "v5": "+ loop-accepted edit"}
    for v, d in deltas.items():
        versions.setdefault(v, {})["delta"] = d
    # synthetic corpus panel: rule-consistency at scale, per archetype. Labels
    # here are construction-derived (the archetype IS one policy clause
    # instantiated), so this measures whether the prompt applies the clause it
    # was written against across surface variation, NOT expert agreement.
    # Suite separation holds: these rows never touch accuracy/EL above.
    synthetic: dict[str, dict] = {}
    for pv, mid, cid, corr in con.execute(
            """SELECT r.prompt_version, r.model_id, r.case_id, r.correct
               FROM runs r JOIN cases c USING(case_id)
               WHERE c.kind='synthetic' AND r.correct IS NOT NULL
                 AND r.run_id IN (SELECT MIN(r2.run_id) FROM runs r2
                                  WHERE r2.case_id=r.case_id
                                    AND r2.prompt_version=r.prompt_version
                                    AND r2.model_id=r.model_id)"""):
        lab = LABELS.get(cid, {})
        arch = lab.get("archetype", "unknown")
        contested = bool(lab.get("contested"))
        cell_s = synthetic.setdefault(f"{pv}|{mid}", {
            "prompt": pv, "model": mid, "n": 0, "correct": 0, "archetypes": {}})
        # contested-label archetypes (a stable cross-version split routed to a
        # human; see the label's contest_note) never count in the headline
        # numerator/denominator; they ship with agreement-with-written-label
        # per archetype so the split itself stays visible
        if not contested:
            cell_s["n"] += 1
            cell_s["correct"] += corr
        a = cell_s["archetypes"].setdefault(
            arch, {"n": 0, "correct": 0, "contested": contested,
                   **({"contest_note": lab.get("contest_note")} if contested else {})})
        a["n"] += 1
        a["correct"] += corr

    # the cost line: what the whole benchmark cost at list prices, from the
    # banked token counts. Free-tier and free-quota columns price at $0 by
    # the PRICE map; claude CLI token counts exclude cache reads (the
    # subscription route bills nothing per call anyway).
    total_cost = 0.0
    total_runs = 0
    unpriced: list[str] = []
    for mid, tin, tout, n in con.execute(
            "SELECT model_id, SUM(COALESCE(tokens_in,0)), SUM(COALESCE(tokens_out,0)), COUNT(*) "
            "FROM runs GROUP BY model_id"):
        # a model with banked runs but no PRICE row is NOT a free tier: it is
        # a missing entry, and pricing it $0 silently undercounts the cost
        # line (the audit caught glm-5.3 riding this exact path). Name it.
        if mid not in PRICE:
            unpriced.append(mid)
        pin, pout = PRICE.get(mid, (0.0, 0.0))
        total_cost += (tin * pin + tout * pout) / 1e6
        total_runs += n
    # the one cost matrix, derived from error_cost so the UI can never carry
    # a hand-copied table that drifts when FA is re-parameterized (the audit
    # found the same nine numbers typed three times across py and jsx)
    decisions = ("APPROVE", "HOLD", "REJECT")
    meta_cost_matrix = {e: {d: error_cost(d, e) for d in decisions} for e in decisions}
    import platform
    contested_n = sum(1 for lab in LABELS.values() if lab.get("contested"))
    flip_gated = 0
    for c in out_cells:
        viols = c.get("violations")
        if isinstance(viols, list) and any("flip" in str(v) for v in viols):
            flip_gated += 1
    meta_routing = {"contested_labels": contested_n, "labels_total": len(LABELS),
                    "flip_gated_cells": flip_gated,
                    "note": "contested labels + flip-gated cells route to a human with the reason attached"}
    meta = {"total_runs": total_runs, "total_cost_usd_list": round(total_cost, 2),
            "review_cost_usd_assumption": REVIEW_COST_USD,
            "routed_to_human": meta_routing,
            # reproducibility metadata: numbers travel with the machine that
            # produced them (latency columns especially are a property of
            # this host + provider routes, and say so in the writeup)
            "environment": {"python": platform.python_version(),
                            "platform": platform.platform(),
                            "machine": platform.machine()},
            "cost_matrix_usd": meta_cost_matrix,
            "unpriced_models": sorted(unpriced),
            "cost_note": "list prices; open-model columns rode free tiers, claude via "
                         "subscription CLI"
                         + (f"; unpriced (excluded from the line): {', '.join(sorted(unpriced))}"
                            if unpriced else "")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"meta": meta, "cells": out_cells, "caseFiles": case_files,
                               "versions": versions, "coverage": coverage,
                               "ladder": ladder, "calibration": calibration,
                               "selfConsistency": self_consistency,
                               "synthetic": sorted(synthetic.values(),
                                                   key=lambda s: (s["model"], s["prompt"])),
                               "clauseMisses": clause_misses}, indent=1))
    print(f"wrote {OUT} with {len(out_cells)} cells / {len(runs)} runs")


if __name__ == "__main__":
    main()
