"""LR baseline: can logistic regression on hand-extracted features match the
LLM cells on the 12-case decision suite?

SPEC.md names this the analyst move that lands hardest: if a tiny linear
model on mechanical features matches the LLM, that bounds where the LLM
earns its cost on THIS suite. Honest framing before any number:
- n=12 with three classes (6 APPROVE / 4 REJECT / 2 HOLD): leave-one-out
  accuracy on 12 points is a smoke signal, not a benchmark.
- The features were chosen by the same person who constructed 8 of the 12
  labels, so feature selection leaks label-authoring judgment. The expert-4
  subset (101, 102, 106, 108) is the only leakage-free read.
- Deterministic: fixed init, full-batch gradient descent, no randomness.

Run: .venv/bin/python experiments/lr_baseline/lr.py  (needs numpy only)
Writes results.json next to this file.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
CASES = ROOT / "data" / "cases"
LABELS = json.loads((ROOT / "data" / "labels.json").read_text())
CLASSES = ["APPROVE", "HOLD", "REJECT"]
DECISION_SUITE = ("golden", "perturbation")

FEATURES = [
    "log_tenure_days",
    "log_at_risk_usd",
    "unverified",
    "confirmed_problem",
    "burst_distinct_instruments",
    "decline_ratio",
    "transfer_out_ratio",
    "strong_fraud_link",
    "owner_changed_recent",
    "watchlist_max_score",
]


def extract(case: dict) -> list[float]:
    acct = case.get("account", {})
    money = case.get("money", {})
    tx = case.get("transactions", [])
    n_tx = max(len(tx), 1)
    declined = sum(1 for t in tx if t.get("status") == "declined")
    transfer_out = sum(t.get("amount_usd", 0.0) for t in tx if t.get("type") == "transfer_out")
    lifetime = max(money.get("lifetime_volume_usd", 0.0), 1.0)
    instruments = {t.get("instrument_last4") for t in tx}
    strong_link = any(
        la.get("status") == "CLOSED_FRAUD" and len(la.get("link_dimensions", [])) >= 2
        for la in case.get("linked_accounts", []))
    wl = case.get("watchlist_hits", [])
    return [
        float(np.log1p(acct.get("tenure_days", 0))),
        float(np.log1p(money.get("at_risk_usd", 0.0))),
        1.0 if acct.get("verification", {}).get("status") != "VERIFIED" else 0.0,
        1.0 if case.get("precomputed", {}).get("confirmed_problem_on_record") else 0.0,
        float(len(instruments)),
        declined / n_tx,
        transfer_out / lifetime,
        1.0 if strong_link else 0.0,
        1.0 if acct.get("owner_changed_days_ago", 9999) < 30 else 0.0,
        max((h.get("score", 0.0) for h in wl), default=0.0),
    ]


def fit_multinomial(x: np.ndarray, y: np.ndarray, l2: float = 0.1,
                    lr: float = 0.1, steps: int = 3000) -> np.ndarray:
    """Full-batch softmax regression, deterministic zero init."""
    n, d = x.shape
    k = len(CLASSES)
    w = np.zeros((d, k))
    onehot = np.eye(k)[y]
    for _ in range(steps):
        logits = x @ w
        logits -= logits.max(axis=1, keepdims=True)
        p = np.exp(logits)
        p /= p.sum(axis=1, keepdims=True)
        grad = x.T @ (p - onehot) / n + l2 * w
        w -= lr * grad
    return w


def main() -> None:
    ids, xs, ys, tiers = [], [], [], []
    for f in sorted(CASES.glob("*.json")):
        case = json.loads(f.read_text())
        cid = case["case_id"]
        lab = LABELS.get(cid, {})
        if lab.get("retired") or lab.get("kind", "golden") not in DECISION_SUITE:
            continue
        if lab.get("expected") not in CLASSES:
            continue
        ids.append(cid)
        xs.append(extract(case))
        ys.append(CLASSES.index(lab["expected"]))
        tiers.append(lab.get("source"))
    x = np.array(xs)
    y = np.array(ys)
    # standardize (fit stats inside each LOO fold's train split)
    preds = []
    for i in range(len(ids)):
        mask = np.ones(len(ids), dtype=bool)
        mask[i] = False
        mu, sd = x[mask].mean(axis=0), x[mask].std(axis=0) + 1e-9
        xtr = np.hstack([(x[mask] - mu) / sd, np.ones((mask.sum(), 1))])
        xte = np.hstack([((x[i] - mu) / sd).reshape(1, -1), np.ones((1, 1))])
        w = fit_multinomial(xtr, y[mask])
        preds.append(int(np.argmax(xte @ w)))
    correct = [int(p == t) for p, t in zip(preds, y)]
    expert_ids = {"CASE-101", "CASE-102", "CASE-106", "CASE-108"}
    expert = [c for c, cid in zip(correct, ids) if cid in expert_ids]
    # full-data fit for the weight table (interpretation aid, not the score)
    mu, sd = x.mean(axis=0), x.std(axis=0) + 1e-9
    w_full = fit_multinomial(np.hstack([(x - mu) / sd, np.ones((len(ids), 1))]), y)
    result = {
        "n": len(ids),
        "loo_accuracy": f"{sum(correct)}/{len(correct)}",
        "loo_accuracy_expert4": f"{sum(expert)}/{len(expert)}",
        "per_case": [
            {"case_id": cid, "expected": CLASSES[t], "predicted": CLASSES[p],
             "correct": bool(c), "label_source": tier}
            for cid, t, p, c, tier in zip(ids, y, preds, correct, tiers)],
        "features": FEATURES,
        "weights_by_class": {
            cls: {feat: round(float(w_full[j, k]), 3) for j, feat in enumerate(FEATURES)}
            for k, cls in enumerate(CLASSES)},
        "caveats": [
            "n=12 LOO is a smoke signal, not a benchmark",
            "features chosen by the label author; expert-4 subset is the only leakage-free read",
            "deterministic full-batch softmax regression, zero init, L2=0.1",
        ],
    }
    out = Path(__file__).resolve().parent / "results.json"
    out.write_text(json.dumps(result, indent=1))
    print(f"LOO accuracy: {result['loo_accuracy']} (expert-4: {result['loo_accuracy_expert4']})")
    for pc in result["per_case"]:
        mark = "ok" if pc["correct"] else f"WRONG (exp {pc['expected']})"
        print(f"  {pc['case_id']:14} -> {pc['predicted']:8} {mark}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
