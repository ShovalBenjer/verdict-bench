#!/usr/bin/env python3
"""Rebuild docs/assets/deck/reliability.png as a two-panel figure.

The old single-curve version collapsed to 3 dots because stated confidence
only ever takes the values 0.9, 0.95, 1.0 (v5conf, gemini-flash, n=21).
That compression is the finding, so panel one shows the pile-up of claims
against measured accuracy, and panel two shows what each claim level
actually earned, with the claimed value drawn beside it.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "docs" / "assets" / "deck"
INK = "#22242a"
INDIGO = "#5b8def"
RED = "#c94f4f"
GOLD = "#b8863f"


def main() -> None:
    db = sqlite3.connect(ROOT / "state" / "verdict.sqlite3")
    rows = db.execute(
        """SELECT confidence, correct FROM runs
           WHERE prompt_version='v5conf' AND model_id='gemini-flash'
             AND confidence IS NOT NULL"""
    ).fetchall()
    assert rows, "no v5conf confidence rows in the ledger"
    n = len(rows)
    mean_conf = sum(r[0] for r in rows) / n
    acc = sum(r[1] for r in rows) / n
    bins: dict[float, list[int]] = {}
    for conf, correct in rows:
        bins.setdefault(conf, []).append(correct)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6))

    # Panel 1: where the claims pile up, vs what the runs earned.
    xs = sorted(bins)
    counts = [len(bins[x]) for x in xs]
    ax1.bar([f"{x:.2f}" for x in xs], counts, color=INDIGO, width=0.55)
    for i, c in enumerate(counts):
        ax1.text(i, c + 0.3, str(c), ha="center", fontsize=11, color=INK)
    ax1.axhline(0, color=INK, lw=0.8)
    ax1.set_title(f"every stated confidence, n={n} runs", fontsize=12)
    ax1.set_xlabel("model states")
    ax1.set_ylabel("runs")
    ax1.text(
        0.03, 0.93,
        f"mean claim {mean_conf:.2f}\nmeasured accuracy {acc:.2f}",
        transform=ax1.transAxes, fontsize=11, va="top", color=RED,
    )

    # Panel 2: what each claim level earned, claim drawn beside it.
    labels = [f"{x:.2f}" for x in xs]
    earned = [sum(bins[x]) / len(bins[x]) for x in xs]
    pos = range(len(xs))
    ax2.bar([p - 0.18 for p in pos], [x for x in xs], width=0.36,
            color="#c9cdd6", label="claimed")
    ax2.bar([p + 0.18 for p in pos], earned, width=0.36,
            color=GOLD, label="earned (share correct)")
    for p, x, e in zip(pos, xs, earned):
        ax2.text(p + 0.18, e + 0.02, f"{e:.2f}\nn={len(bins[x])}",
                 ha="center", fontsize=9.5, color=INK)
    ax2.set_xticks(list(pos), labels)
    ax2.set_ylim(0, 1.12)
    ax2.set_xlabel("stated confidence")
    ax2.set_title("claimed vs earned, per claim level", fontsize=12)
    ax2.legend(loc="lower right", fontsize=10)

    fig.suptitle(
        "gemini-flash v5conf: claims live in a 0.90-1.00 band; runs earn 0.90",
        fontsize=13, y=1.02,
    )
    fig.tight_layout()
    out = DECK / "reliability.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"{out} rebuilt: {n} runs, bins {dict((x, len(bins[x])) for x in xs)}")


if __name__ == "__main__":
    main()
