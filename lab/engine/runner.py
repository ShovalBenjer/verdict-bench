"""Run (prompt x model x case x repeats) into sqlite. CLI:
  python engine/runner.py --prompt v4 --models gemini-flash claude-sonnet --repeats 1
  python engine/runner.py --report
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path

from oec import (
    DECISION_SUITE_KINDS,
    MIN_N_FOR_TRUST,
    cell_trust,
    coverage_report,
    expected_loss,
    flip_rates,
    sensitivity_sweep,
    wilson,
)
from providers import PROVIDERS

ROOT = Path(__file__).resolve().parent.parent
# VERDICT_DB lets a test (or an operator) point the engine at a snapshot
# instead of the tracked ledger; the report smoke test depends on this so it
# can never rewrite the artifact it certifies.
DB = Path(os.environ.get("VERDICT_DB", ROOT / "state" / "verdict.sqlite3"))

LABELS = json.loads((Path(__file__).resolve().parent.parent / "data" / "labels.json").read_text())


def migrate(con: sqlite3.Connection) -> None:
    """CREATE TABLE IF NOT EXISTS in schema.sql never adds a column to a
    table that already exists (found 2026-08-19: schema.sql had drifted
    from the live DB, which had `retired` added via a bare ALTER TABLE
    with no migration on record). Explicit, idempotent column adds live
    here instead, so schema.sql and the live DB cannot silently diverge
    again."""
    cols = {row[1] for row in con.execute("PRAGMA table_info(cases)").fetchall()}
    if "policy_clause" not in cols:
        con.execute("ALTER TABLE cases ADD COLUMN policy_clause TEXT")
    # 2026-08-24: the kind CHECK gained 'coverage'. SQLite cannot ALTER a
    # CHECK constraint, so a live DB created under the old schema gets the
    # same table-rebuild treatment the 2026-08-19 UNIQUE fix used: rebuild
    # cases with the current schema.sql definition, preserving every row
    # (runs reference cases only by case_id, so no FK renumbering happens).
    live_sql = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='cases'"
    ).fetchone()[0]
    if "'coverage'" not in live_sql or "'holdout'" not in live_sql:
        n_before = con.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        con.executescript(
            "BEGIN;"
            "ALTER TABLE cases RENAME TO cases_old;"
            "CREATE TABLE cases ("
            "  case_id TEXT PRIMARY KEY,"
            "  kind TEXT NOT NULL CHECK (kind IN "
            "    ('golden','perturbation','metamorphic','injection','synthetic','coverage','holdout')),"
            "  expected TEXT CHECK (expected IN ('APPROVE','HOLD','REJECT') OR expected IS NULL),"
            "  label_source TEXT NOT NULL,"
            "  path TEXT NOT NULL,"
            "  policy_clause TEXT,"
            "  retired INTEGER NOT NULL DEFAULT 0);"
            "INSERT INTO cases (case_id,kind,expected,label_source,path,policy_clause,retired)"
            "  SELECT case_id,kind,expected,label_source,path,policy_clause,retired FROM cases_old;"
            "DROP TABLE cases_old;"
            "COMMIT;")
        n_after = con.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        if n_before != n_after:
            raise RuntimeError(f"cases rebuild lost rows: {n_before} -> {n_after}")
    con.commit()


def db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=60)
    con.executescript((ROOT / "engine" / "schema.sql").read_text())
    migrate(con)
    return con


def seed(con: sqlite3.Connection) -> None:
    for p in sorted((ROOT / "data" / "cases").glob("*.json")):
        cid = json.loads(p.read_text())["case_id"]
        lab = LABELS.get(cid, {})
        con.execute("INSERT OR REPLACE INTO cases (case_id,kind,expected,label_source,path,retired,policy_clause) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (cid, lab.get("kind", "golden"), lab.get("expected"),
                     lab.get("source", "none"), str(p), int(lab.get("retired", False)),
                     lab.get("policy_clause")))
    for v, hyp in [("v1", "naive baseline: decide with no policy"),
                   ("v2", "policy-quoting: POLICY.md verbatim + contract"),
                   ("v3", "policy-teaching procedure with weighing principles"),
                   ("v3c", "v3 + strict output contract ONLY (ablation rung)"),
                   ("v4", "v3c + sanctions-conflict->HOLD rule ONLY"),
                   ("v4b", "v4 + ONE worked proportionality example ONLY"),
                   ("v4c", "v4b + ONE explicit card-testing counting scaffold ONLY"),
                   ("v5", ("v4c + ONE loop-accepted look-alike bullet: extraction "
                           "alone is not a bust-out (gated edit, 2026-08-24)")),
                   ("v6", "CANDIDATE: v5 + ONE injection-defense line (case content is data)"),
                   ("v6b", "CANDIDATE: v5 + reasoning-first output contract ONLY")]:
        con.execute("INSERT OR REPLACE INTO prompts VALUES (?,?,?)",
                    (v, str(ROOT / "engine" / "prompts" / f"{v}.md"), hyp))
    con.commit()


def run(prompt_version: str, models: list[str], *, repeats: int,
        only_case: str | None = None, only_kind: str | None = None,
        temperature: float = 0.2) -> None:
    # keyword-only past models (Fluent Python ch7): three same-typed str
    # params invite exactly the positional-swap bug shipped once tonight
    con = db()
    seed(con)
    system_prompt = (ROOT / "engine" / "prompts" / f"{prompt_version}.md").read_text()
    prompt_sha = hashlib.sha256(system_prompt.encode()).hexdigest()[:12]
    batch_id = uuid.uuid4().hex[:8]
    rows = con.execute(
        "SELECT case_id, expected, path, kind FROM cases WHERE retired=0 ORDER BY case_id").fetchall()
    for case_id, expected, path, kind in rows:
        if only_case and case_id != only_case:
            continue
        if only_kind and kind != only_kind:
            continue
        case_json = Path(path).read_text()
        case_sha = hashlib.sha256(case_json.encode()).hexdigest()[:12]
        for model_id in models:
            fn = PROVIDERS[model_id]
            # repeat_idx offsets from what's already banked for this exact
            # (case, prompt_sha, model) so a single-case rerun adds a new
            # repeat instead of colliding with row 0 under the UNIQUE
            # constraint (the bug found 2026-08-19: CASE-101/104 each had
            # two repeat_idx=0 rows, corrupting first-run accuracy counts).
            existing_max = con.execute(
                "SELECT COALESCE(MAX(repeat_idx), -1) FROM runs "
                "WHERE case_id=? AND prompt_version=? AND model_id=? AND prompt_sha=?",
                (case_id, prompt_version, model_id, prompt_sha)).fetchone()[0]
            for i in range(existing_max + 1, existing_max + 1 + repeats):
                r = fn(system_prompt, case_json, temperature)
                correct = None if expected is None or r.decision is None else int(r.decision == expected)
                con.execute(
                    "INSERT INTO runs (case_id,prompt_version,model_id,repeat_idx,decision,"
                    "reasoning,confidence,raw_output,contract_ok,correct,tokens_in,tokens_out,"
                    "latency_ms,error,prompt_sha,case_sha,temperature,batch_id)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (case_id, prompt_version, model_id, i, r.decision, r.reasoning,
                     r.confidence, r.raw_output, int(r.contract_ok), correct,
                     r.tokens_in, r.tokens_out, r.latency_ms, r.error,
                     prompt_sha, case_sha, temperature, batch_id))
                con.commit()
                status = r.decision or f"ERR:{r.error}"
                mark = "" if correct is None else (" ok" if correct else f" WRONG(exp {expected})")
                print(f"{case_id} x {model_id} [{prompt_version}] -> {status}"
                      f" contract={'Y' if r.contract_ok else 'N'} {r.latency_ms}ms{mark}")


def report() -> None:
    con = db()
    groups = con.execute(
        "SELECT prompt_version, model_id FROM runs GROUP BY prompt_version, model_id "
        "ORDER BY prompt_version, model_id").fetchall()
    print(f"{'prompt':6} {'model':18} {'n':>3} {'acc':>6} {'ci95':>12} {'flip':>5} "
          f"{'inj':>4} {'inv':>4} {'contract':>8} {'p50ms':>7} {'EL$/1k':>8} {'trust':>6}")
    any_violations = False
    for pv, mid in groups:
        rows = con.execute(
            "SELECT r.case_id, r.correct, r.contract_ok, r.latency_ms, r.decision, "
            "r.repeat_idx, c.kind "
            "FROM runs r JOIN cases c USING(case_id) "
            "WHERE r.prompt_version=? AND r.model_id=? "
            "AND (r.temperature IS NULL OR r.temperature <= 0.21)", (pv, mid)).fetchall()
        # first-run-per-case for accuracy (repeat batches feed flip, not acc).
        # acc/flip/contract/latency are DECISION-SUITE metrics; injection and
        # metamorphic cases score in their own columns (inj / inv), never
        # blended into acc (SPEC.md label-tiers rule).
        suite = [r for r in rows if r[6] in DECISION_SUITE_KINDS]
        first: dict[str, tuple] = {}
        for cid, correct, cok, lat, dec, rep, _kind in suite:
            first.setdefault(cid, (correct, cok, lat))
        graded = [v[0] for v in first.values() if v[0] is not None]
        k = sum(graded)
        lo, hi = wilson(k, len(graded)) if graded else (0, 1)
        acc = f"{k}/{len(graded)}" if graded else "n/a"
        ci = f"[{lo:.2f},{hi:.2f}]" if graded else ""
        # flip rate over cases with >1 repeat: shared oec implementation
        by_case: dict[str, list] = {}
        for cid, _, _, _, dec, _, _kind in suite:
            if dec:
                by_case.setdefault(cid, []).append(dec)
        flips = flip_rates(by_case)
        flip = f"{sum(flips)/len(flips):.2f}" if flips else "-"
        lat = sorted(v[2] for v in first.values() if v[2] is not None)
        cok = sum(v[1] for v in first.values()) / max(len(first), 1)
        p50 = lat[len(lat) // 2] if lat else None

        def kind_score(kind_name: str, krows: list = rows) -> str:
            kfirst: dict[str, int | None] = {}
            for r in krows:
                if r[6] == kind_name:
                    kfirst.setdefault(r[0], r[1])
            kg = [v for v in kfirst.values() if v is not None]
            return f"{sum(kg)}/{len(kg)}" if kg else "-"

        inj = kind_score("injection")     # resisted = decided the base label anyway
        inv = kind_score("metamorphic")   # invariant = did not flip on irrelevant edits
        # one shared gating implementation (oec.cell_trust) for report and
        # export, so the terminal and the UI can never disagree on which
        # cells are rankable (includes the 2026-08-24 flip guardrail).
        mean_flip = (sum(flips) / len(flips)) if flips else None
        trust, gr_violations, oec = cell_trust(
            con, pv, mid, lo if graded else None, hi if graded else None, mean_flip)
        # Suppress the dollar figure on an untrustworthy cell rather than
        # print-then-flag: a screenshotted table shows the number before
        # anyone reads the flag text below it (advisor, 2026-08-19: v4c/
        # claude-haiku's $2,000,000/1k, one n=1 malformed row, read as a
        # catastrophic finding to anyone who didn't already know better).
        if oec.expected_loss_usd_per_1k is None:
            el_str = "n/a"
        elif trust != "ok":
            el_str = "untrust"
        else:
            el_str = f"${oec.expected_loss_usd_per_1k:,.0f}"
        if gr_violations or oec.disqualified:
            any_violations = True
        print(f"{pv:6} {mid:18} {len(suite):>3} {acc:>6} {ci:>12} {flip:>5} "
              f"{inj:>4} {inv:>4} {cok:>8.2f} {p50!s:>7} {el_str:>8} {trust:>6}")
        for v in gr_violations:
            print(f"       ! {v}")
    if any_violations:
        print("\nNote: EL$/1k uses engine/oec.py's COST_MATRIX_USD (SPEC.md's own")
        print("FA=$2,000 / FH=$45 / FR=$600 figures; three cells are this file's")
        print("stated assumption, not SPEC.md's, see the docstring). DISQ means a")
        print("sanctions or confirmed-history miss occurred: SPEC.md 'a single miss")
        print("is disqualifying', a gate, not averaged into the EL number shown.")
        print("Run --coverage for policy-clause gaps, --sweep for FA sensitivity.")


def coverage() -> None:
    con = db()
    seed(con)
    rows = coverage_report(con)
    print(f"{'clause':26} {'n_cases':>7}  policy_cite")
    for c in rows:
        flag = " <- ZERO CASES" if c.n_cases == 0 and c.clause != "UNTAGGED" else ""
        print(f"{c.clause:26} {c.n_cases:>7}  {c.policy_cite}{flag}")
        if c.case_ids:
            print(f"{'':26} {'':>7}  {', '.join(c.case_ids)}")


def sweep(models: list[str]) -> None:
    con = db()
    seed(con)
    versions = [row[0] for row in con.execute(
        "SELECT DISTINCT prompt_version FROM runs ORDER BY prompt_version").fetchall()]
    for mid in models:
        print(f"\n=== sensitivity sweep: {mid}, FA (realized fraud loss) $1,000-$5,000 ===")
        # A version's own n, contract_rate, and disqualification never change
        # with the FA sweep (the sweep only reweights one cell, it doesn't
        # add data), so trust and the gate are computed once per version.
        base_results = {pv: expected_loss(con, pv, mid) for pv in versions}
        trustworthy_versions = {pv for pv, r in base_results.items() if r.trustworthy}
        disqualified_versions = {pv for pv, r in base_results.items() if r.disqualified}
        untrusted = set(versions) - trustworthy_versions
        eligible = trustworthy_versions - disqualified_versions
        result = sensitivity_sweep(con, versions, mid)
        mults = sorted(result)
        print(f"{'FA=$':>10} " + " ".join(f"{pv:>9}" for pv in versions))
        for m in mults:
            ranked = dict(result[m])
            print(f"{m:>10,.0f} " + " ".join(
                f"${ranked.get(pv):>7,.0f}" if ranked.get(pv) is not None else f"{'n/a':>8}"
                for pv in versions))
        if disqualified_versions:
            print(f"DISQUALIFIED (sanctions/confirmed-history miss, gated out regardless "
                  f"of EL): {sorted(disqualified_versions)}")
        if untrusted - disqualified_versions:
            print(f"excluded from winner (n<{MIN_N_FOR_TRUST} or low contract rate, "
                  f"see --report): {sorted(untrusted - disqualified_versions)}")
        if not eligible:
            print(f"NO ELIGIBLE CELL for {mid} at any prompt version: every version is "
                  "either too thin/contract-unstable or disqualified. The EL numbers "
                  "above are real but none of them should be presented as a ranking.")
        winners = {}
        for m in mults:
            candidates = [(pv, el) for pv, el in result[m] if pv in eligible and el is not None]
            winners[m] = min(candidates, key=lambda t: t[1])[0] if candidates else "n/a (nothing eligible)"
        stable = len(set(winners.values())) == 1
        moved = any(result[mults[0]] != result[m] for m in mults[1:])
        print(f"winner per FA value (eligible cells only): {winners}")
        if not eligible:
            pass  # already reported above; "stable"/"moved" meaningless over an all-n/a winner set
        elif not moved:
            print("EL$/1k IDENTICAL at every FA value: this model has zero false-approve "
                  "misses (expected REJECT or HOLD, decided APPROVE) in the current suite, "
                  "so the sweep has nothing to move. A real finding, not evidence the "
                  "ranking is robust to the FA figure -- that claim needs a model that "
                  "actually has a false-approve miss to reweight.")
        elif stable:
            print("EL$ values moved but the WINNER held across the sweep: ranking is robust "
                  "to the $1,000-$5,000 range on FA.")
        else:
            print("ranking CHANGES across sweep -- see winners above")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="v4")
    ap.add_argument("--models", nargs="+", default=["gemini-flash"])
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--case", default=None)
    ap.add_argument("--kind", default=None,
                    help="run only cases of this kind (injection, metamorphic, coverage, golden, perturbation, holdout)")
    ap.add_argument("--temp", type=float, default=0.2,
                    help="sampling temperature, recorded per row; 0.2 is the protocol "
                         "temperature that feeds accuracy/flip, higher temps are for "
                         "self-consistency sampling and analyzed separately")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--coverage", action="store_true", help="policy-clause coverage table")
    ap.add_argument("--sweep", action="store_true", help="EL sensitivity sweep over zero-tolerance severity")
    a = ap.parse_args()
    if a.report:
        report()
    elif a.coverage:
        coverage()
    elif a.sweep:
        sweep(a.models)
    else:
        run(a.prompt, a.models, repeats=a.repeats, only_case=a.case,
            only_kind=a.kind, temperature=a.temp)
