#!/usr/bin/env python3
"""PaySim-style population loss simulation over the measured benchmark.

The scale question ("52 cases is not a book") gets answered the only honest
way available without license-gated data on disk (tools/fetch_data/
PROVENANCE.md): a Monte Carlo population whose BEHAVIORAL kernel is
measured, not assumed: each archetype's decision distribution comes from
the banked LLM runs on the synthetic corpus (state/verdict.sqlite3), and
what IS assumed is named and swept: the archetype prevalence mix and the
per-case fraud exposure distribution (lognormal fit to the corpus's own
at_risk_usd values, fit parameters printed).

Two pricing modes per scenario, divergence shown on purpose:
  matrix   flat SPEC costs per error type (the benchmark's own framing)
  exposure FA priced at the case's drawn exposure (dollar-weighted reality,
           where one large bust-out dominates a thousand small insults)

Outputs state/population_sim.json (consumed by the notebook) and a table.
Deterministic: random.Random(SEED). No API calls, no network.

Run: python3 tools/population_sim.py [--population 1000000]
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
from export import error_cost  # noqa: E402

SEED = 20260824
DECISIONS = ("APPROVE", "HOLD", "REJECT")

# Named assumption, swept: what share of a real review book each archetype
# family occupies. The writeup's own citation puts real fraud prevalence
# under 1%; three scenarios bracket it. Within each family the archetypes
# split evenly. Contested data_quality cases are carried as their own bucket
# so a scenario can price them under EITHER reading of the policy.
SCENARIOS = {
    "fraud_0.1pct": {"fraud": 0.001, "hold_risk": 0.02, "contested": 0.005},
    "fraud_0.5pct": {"fraud": 0.005, "hold_risk": 0.03, "contested": 0.01},
    "fraud_2pct": {"fraud": 0.02, "hold_risk": 0.05, "contested": 0.02},
}

FRAUD_ARCHETYPES = ("sanctions_true_match", "card_testing", "bust_out",
                    "confirmed_prior_fraud", "fraud_linked", "probe_then_scale")
HOLD_ARCHETYPES = ("unverifiable_identity", "doc_inconsistency_new")
APPROVE_ARCHETYPES = ("clean_established", "watchlist_false_positive",
                      "minor_anomaly_established", "incidental_overlap")
CONTESTED_ARCHETYPE = "data_quality_flag"
EXPECTED = {a: "REJECT" for a in FRAUD_ARCHETYPES}
EXPECTED |= {a: "HOLD" for a in HOLD_ARCHETYPES}
EXPECTED |= {a: "APPROVE" for a in APPROVE_ARCHETYPES}


def measured_kernel(con: sqlite3.Connection, prompt_version: str,
                    model_id: str) -> dict[str, dict[str, float]]:
    """Per-archetype decision distribution from the banked synthetic runs:
    the measured heart of the simulation. Raises if an archetype has no
    runs for this cell rather than inventing behavior."""
    labels = json.loads((ROOT / "data" / "labels.json").read_text())
    counts: dict[str, dict[str, int]] = {}
    for cid, dec in con.execute(
            """SELECT r.case_id, r.decision FROM runs r JOIN cases c USING(case_id)
               WHERE c.kind='synthetic' AND r.prompt_version=? AND r.model_id=?
                 AND r.decision IS NOT NULL""", (prompt_version, model_id)):
        arch = labels[cid]["archetype"]
        counts.setdefault(arch, {d: 0 for d in DECISIONS})
        counts[arch][dec] = counts[arch].get(dec, 0) + 1
    kernel = {}
    for arch in (*FRAUD_ARCHETYPES, *HOLD_ARCHETYPES, *APPROVE_ARCHETYPES,
                 CONTESTED_ARCHETYPE):
        if arch not in counts or not sum(counts[arch].values()):
            raise RuntimeError(
                f"no banked synthetic runs for archetype {arch} on "
                f"{prompt_version}|{model_id}; run the corpus first")
        total = sum(counts[arch].values())
        kernel[arch] = {d: counts[arch].get(d, 0) / total for d in DECISIONS}
    return kernel


def exposure_fit(con: sqlite3.Connection) -> tuple[float, float]:
    """Lognormal mu/sigma fit to the corpus's own nonzero at_risk_usd
    values: the exposure assumption is grounded in the one dataset this
    repo actually holds, and says so."""
    vals = []
    for (path,) in con.execute("SELECT path FROM cases"):
        try:
            v = json.loads(Path(path).read_text()).get("money", {}).get("at_risk_usd", 0)
            if v and v > 0:
                vals.append(float(v))
        except (OSError, json.JSONDecodeError):
            continue
    logs = [math.log(v) for v in vals]
    mu = sum(logs) / len(logs)
    var = sum((x - mu) ** 2 for x in logs) / max(len(logs) - 1, 1)
    return mu, math.sqrt(var)


def simulate(kernel: dict, mix: dict[str, float], n: int, mu: float,
             sigma: float, rng: random.Random) -> dict:
    """Draw a population, decide each case by the measured kernel, price
    both ways. Contested cases are priced under BOTH policy readings
    (HOLD-is-right vs APPROVE-is-right) and reported separately: the
    simulation refuses to resolve what the policy owner has not."""
    p_fraud, p_hold, p_cont = mix["fraud"], mix["hold_risk"], mix["contested"]
    loss_matrix = 0.0
    loss_exposure = 0.0
    contested_delta = {"hold_right": 0.0, "approve_right": 0.0}
    decided = {d: 0 for d in DECISIONS}
    for _ in range(n):
        u = rng.random()
        if u < p_fraud:
            arch = rng.choice(FRAUD_ARCHETYPES)
        elif u < p_fraud + p_hold:
            arch = rng.choice(HOLD_ARCHETYPES)
        elif u < p_fraud + p_hold + p_cont:
            arch = CONTESTED_ARCHETYPE
        else:
            arch = rng.choice(APPROVE_ARCHETYPES)
        dist = kernel[arch]
        r = rng.random()
        decision = ("APPROVE" if r < dist["APPROVE"]
                    else "HOLD" if r < dist["APPROVE"] + dist["HOLD"]
                    else "REJECT")
        decided[decision] += 1
        if arch == CONTESTED_ARCHETYPE:
            contested_delta["hold_right"] += error_cost(decision, "HOLD")
            contested_delta["approve_right"] += error_cost(decision, "APPROVE")
            continue
        expected = EXPECTED[arch]
        loss_matrix += error_cost(decision, expected)
        if expected == "REJECT" and decision != "REJECT":
            exposure = math.exp(rng.gauss(mu, sigma))
            loss_exposure += exposure if decision == "APPROVE" else exposure * 0.25
        else:
            loss_exposure += error_cost(decision, expected)
    return {
        "population": n,
        "decided": decided,
        "hold_rate": round(decided["HOLD"] / n, 4),
        "loss_matrix_per_1k": round(loss_matrix / n * 1000, 2),
        "loss_exposure_per_1k": round(loss_exposure / n * 1000, 2),
        "contested_cost_per_1k_if_hold_right": round(contested_delta["hold_right"] / n * 1000, 2),
        "contested_cost_per_1k_if_approve_right": round(contested_delta["approve_right"] / n * 1000, 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--population", type=int, default=1_000_000)
    ap.add_argument("--cells", nargs="+", default=["v5|gemini-flash", "v1|gemini-flash"])
    a = ap.parse_args()
    con = sqlite3.connect(ROOT / "state" / "verdict.sqlite3")
    mu, sigma = exposure_fit(con)
    out = {"seed": SEED, "population": a.population,
           "exposure_fit": {"lognormal_mu": round(mu, 4), "lognormal_sigma": round(sigma, 4),
                            "source": "corpus's own nonzero at_risk_usd values"},
           "scenarios": {}}
    for cell in a.cells:
        pv, mid = cell.split("|")
        kernel = measured_kernel(con, pv, mid)
        for name, mix in SCENARIOS.items():
            rng = random.Random(SEED)
            res = simulate(kernel, mix, a.population, mu, sigma, rng)
            out["scenarios"][f"{cell}|{name}"] = {"mix": mix, **res}
            print(f"{cell} {name}: matrix ${res['loss_matrix_per_1k']}/1k, "
                  f"exposure-priced ${res['loss_exposure_per_1k']}/1k, "
                  f"hold {res['hold_rate']:.1%}")
    (ROOT / "state" / "population_sim.json").write_text(json.dumps(out, indent=1))
    print(f"wrote state/population_sim.json ({len(out['scenarios'])} scenarios)")


if __name__ == "__main__":
    main()
