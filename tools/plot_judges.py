#!/usr/bin/env python3
"""Build docs/assets/deck/judge_triangulation.png: three judges, three rubric
axes. The story is discrimination: gemini-flash saturates at 5.0 on every axis
(a dead instrument, excluded from averages), claude-haiku and phi-4 spread.
Replaces clause_citation.png on the judge slide, where a wall of 1.0 bars
said nothing."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "docs" / "assets" / "deck"
AXES = ("fidelity", "evidence", "proportionality")
JUDGES = ("gemini-flash", "claude-haiku", "hf-phi-4")
COLORS = {"gemini-flash": "#c9cdd6", "claude-haiku": "#5b8def", "hf-phi-4": "#b8863f"}
LABELS = {"gemini-flash": "gemini-flash (saturated, excluded)",
          "claude-haiku": "claude-haiku", "hf-phi-4": "phi-4 (microsoft)"}


def main() -> None:
    db = sqlite3.connect(ROOT / "state" / "verdict.sqlite3")
    means: dict[str, list[float]] = {}
    ns: dict[str, int] = {}
    for j in JUDGES:
        row = db.execute(
            f"SELECT AVG(fidelity), AVG(evidence), AVG(proportionality), COUNT(*) "
            f"FROM judgments WHERE judge_model=?", (j,)).fetchone()
        assert row and row[0] is not None, f"no judgments for {j}"
        means[j] = [row[0], row[1], row[2]]
        ns[j] = row[3]

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    width = 0.26
    for k, j in enumerate(JUDGES):
        xs = [i + (k - 1) * width for i in range(len(AXES))]
        bars = ax.bar(xs, means[j], width=width, color=COLORS[j],
                      label=f"{LABELS[j]}, n={ns[j]}")
        for b, v in zip(bars, means[j]):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.06, f"{v:.1f}",
                    ha="center", fontsize=10)
    ax.axhline(5.0, ls="--", lw=1, c="#c94f4f")
    ax.text(2.42, 5.04, "ceiling", fontsize=9, c="#c94f4f", ha="right")
    ax.set_xticks(range(len(AXES)), AXES)
    ax.set_ylim(0, 5.6)
    ax.set_ylabel("mean rubric score (1-5)")
    ax.set_title("three judge families on three rubric axes: one saturates, two discriminate")
    ax.legend(loc="lower left", fontsize=9)
    fig.tight_layout()
    out = DECK / "judge_triangulation.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(out, {j: [round(v, 2) for v in means[j]] for j in JUDGES})


if __name__ == "__main__":
    main()
