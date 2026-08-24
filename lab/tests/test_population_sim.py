"""Oracles for the population simulation: deterministic under its seed,
conserving (every drawn case gets exactly one decision), refusing to run
on archetypes with no measured behavior, and pricing the two modes with
the divergence the design promises (exposure pricing must dominate matrix
pricing when the drawn exposures are large)."""
import math
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "engine"))
from population_sim import (  # noqa: E402
    APPROVE_ARCHETYPES,
    CONTESTED_ARCHETYPE,
    FRAUD_ARCHETYPES,
    HOLD_ARCHETYPES,
    SCENARIOS,
    simulate,
)


def perfect_kernel() -> dict:
    k = {}
    for a in FRAUD_ARCHETYPES:
        k[a] = {"APPROVE": 0.0, "HOLD": 0.0, "REJECT": 1.0}
    for a in HOLD_ARCHETYPES:
        k[a] = {"APPROVE": 0.0, "HOLD": 1.0, "REJECT": 0.0}
    for a in APPROVE_ARCHETYPES:
        k[a] = {"APPROVE": 1.0, "HOLD": 0.0, "REJECT": 0.0}
    k[CONTESTED_ARCHETYPE] = {"APPROVE": 1.0, "HOLD": 0.0, "REJECT": 0.0}
    return k


def test_deterministic_and_conserving():
    kern = perfect_kernel()
    mix = SCENARIOS["fraud_0.5pct"]
    a = simulate(kern, mix, 20_000, 7.5, 1.0, random.Random(1))
    b = simulate(kern, mix, 20_000, 7.5, 1.0, random.Random(1))
    assert a == b
    assert sum(a["decided"].values()) == 20_000


def test_perfect_kernel_prices_zero_outside_contested():
    res = simulate(perfect_kernel(), SCENARIOS["fraud_0.5pct"], 50_000,
                   7.5, 1.0, random.Random(2))
    assert res["loss_matrix_per_1k"] == 0.0
    assert res["loss_exposure_per_1k"] == 0.0
    # contested cards are still priced under both readings, never silently
    assert res["contested_cost_per_1k_if_hold_right"] >= 0.0


def test_exposure_pricing_dominates_matrix_on_big_fraud_misses():
    # a kernel that always APPROVEs fraud, with exposures drawn around
    # e^9 (~$8k) far above the flat $2,000 FA: exposure pricing must exceed
    # matrix pricing, which is the design's whole point
    kern = perfect_kernel()
    for a in FRAUD_ARCHETYPES:
        kern[a] = {"APPROVE": 1.0, "HOLD": 0.0, "REJECT": 0.0}
    res = simulate(kern, SCENARIOS["fraud_2pct"], 50_000, 9.0, 0.3,
                   random.Random(3))
    assert res["loss_exposure_per_1k"] > res["loss_matrix_per_1k"] > 0


def test_missing_archetype_refuses():
    import sqlite3

    from population_sim import measured_kernel
    con = sqlite3.connect(":memory:")
    con.executescript((ROOT / "engine" / "schema.sql").read_text())
    with pytest.raises(RuntimeError, match="no banked synthetic runs"):
        measured_kernel(con, "vX", "nobody")


def test_scenario_mixes_are_probabilities():
    for name, mix in SCENARIOS.items():
        assert 0 < sum(mix.values()) < 0.2, name  # risk buckets are minorities
        assert all(0 < v < 1 for v in mix.values()), name


def test_lognormal_exposure_sane():
    # the exposure draw is a plain lognormal: median e^mu
    rng = random.Random(4)
    draws = [math.exp(rng.gauss(8.0, 0.5)) for _ in range(10_000)]
    med = sorted(draws)[5000]
    assert 0.8 * math.exp(8.0) < med < 1.2 * math.exp(8.0)
