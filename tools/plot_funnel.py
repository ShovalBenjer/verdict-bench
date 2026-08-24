#!/usr/bin/env python3
"""Rebuild docs/assets/deck/funnel.png: the funnel plot with selective labels.

The notebook's version labeled every cell, and the in-funnel cluster at the
top stacked half a dozen names into an unreadable pile (operator: "spaced too
tightly, names colliding"). The deck copy labels only the points that carry
information: cells below the 95% lower limit, the zero-accuracy outlier, and
the champion cell. The in-funnel cluster stays anonymous, which is the point
of a funnel plot."""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "docs" / "assets" / "deck"
SUITE = "kind IN ('golden','perturbation')"
TEMP = "(temperature IS NULL OR temperature<=0.21)"


def main() -> None:
    db = sqlite3.connect(ROOT / "state" / "verdict.sqlite3")
    rows = db.execute(
        f"""SELECT prompt_version, model_id, COUNT(*), AVG(correct)
            FROM runs JOIN cases USING(case_id)
            WHERE {SUITE} AND {TEMP} AND correct IS NOT NULL
            GROUP BY prompt_version, model_id"""
    ).fetchall()
    p0 = db.execute(
        f"""SELECT AVG(correct) FROM runs JOIN cases USING(case_id)
            WHERE {SUITE} AND {TEMP} AND correct IS NOT NULL"""
    ).fetchone()[0]

    fig, ax = plt.subplots(figsize=(9.8, 5.2))
    nmax = max(r[2] for r in rows)
    ns = list(range(1, nmax + 4))
    for z, style, lab in ((1.96, "--", "luck band, 95%"), (3.09, ":", "luck band, 99.8%")):
        ax.plot(ns, [min(1, p0 + z * math.sqrt(p0 * (1 - p0) / n)) for n in ns],
                style, c="gray", lw=1, label=lab)
        ax.plot(ns, [max(0, p0 - z * math.sqrt(p0 * (1 - p0) / n)) for n in ns],
                style, c="gray", lw=1)
    ax.axhline(p0, c="gray", lw=1)

    labeled = []
    seen_kind = set()
    for pv, model, n, acc in rows:
        lo = p0 - 1.96 * math.sqrt(p0 * (1 - p0) / n)
        outlier = acc < lo or acc <= 0.05
        champion = pv == "v5" and model == "gemini-flash"
        kind = "champion" if champion else ("outlier" if outlier else "cell")
        label_for_legend = {
            "cell": "one prompt x model cell, within the luck band",
            "outlier": "below the band: a real underperformer",
            "champion": "v5 + gemini-flash, the shipped pairing",
        }[kind] if kind not in seen_kind else None
        seen_kind.add(kind)
        ax.scatter(n, acc, s=46,
                   c="#c94f4f" if outlier else ("#b8863f" if champion else "#5b8def"),
                   zorder=3, label=label_for_legend)
        if outlier or champion:
            labeled.append((n, acc, f"{pv} | {model.replace('-super-49b','').replace('-3.3-70b','')}"))
    # global collision pass: push any label that lands near an earlier one
    labeled.sort(key=lambda t: (t[0], -t[1]))
    placed: list[tuple[float, float]] = []
    for n, acc, text in labeled:
        y = acc
        while any(abs(px - n) < 11 and abs(py - y) < 0.065 for px, py in placed):
            y -= 0.07
        placed.append((n, y))
        left = n > nmax * 0.8
        ax.annotate(text, (n, acc),
                    xytext=(n - 0.8 if left else n + 0.8, y - 0.015),
                    ha="right" if left else "left", fontsize=9.5,
                    arrowprops=dict(arrowstyle="-", lw=0.6, color="#888")
                    if abs(y - acc) > 0.02 else None)

    ax.set_xlabel("cases graded (n)")
    ax.set_ylabel("accuracy")
    ax.set_ylim(-0.06, 1.08)
    ax.set_title("every dot is one prompt x model result; the curves show how far\n"
                 f"a cell can drift from the shared rate ({p0:.2f}) by luck alone at that sample size")
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    out = DECK / "funnel.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(out, f"{len(rows)} cells, {len(labeled)} labeled")


if __name__ == "__main__":
    main()
