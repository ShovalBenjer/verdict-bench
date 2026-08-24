"""DSPy comparison arm: signature, program, data loading, and the exact-match
metric. Isolated under experiments/dspy_arm/ only; does not import or touch
anything under engine/, state/, assignment/, docs/, or tests/.

Case data: data/cases/*.json (keyed by the case_id field inside each file, not
the filename). Labels: data/labels.json, field "expected"; any case with
"retired": true is excluded, matching the 12 active cases the hand ladder uses.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import dspy

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = REPO_ROOT / "data" / "cases"
LABELS_PATH = REPO_ROOT / "data" / "labels.json"
POLICY_PATH = REPO_ROOT / "assignment" / "case-study" / "case-study" / "POLICY.md"

VALID_DECISIONS = {"APPROVE", "HOLD", "REJECT"}

# The leave-4-out split named in the task: the 4 expert-labeled cases are the
# held-out eval set, the remaining 8 active cases (adjudicated + construction
# sourced) are what the optimizer sees during compilation.
EXPERT_EVAL_IDS = ["CASE-101", "CASE-102", "CASE-106", "CASE-108"]


def read_env_key(name: str) -> str:
    """Same shape as engine/providers.py:_env -- env var first, ~/.env
    fallback, never prints or logs the value."""
    v = os.environ.get(name, "")
    if v:
        return v
    env_path = os.path.expanduser("~/.env")
    if os.path.exists(env_path):
        with open(env_path) as fh:
            for line in fh:
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError(f"missing credential {name}")


def load_policy_text() -> str:
    return POLICY_PATH.read_text()


def load_active_cases() -> dict[str, dict]:
    """Returns {case_id: {"case_json": <raw json text>, "expected": <label>}}
    for the 12 active (non-retired) cases, keyed by the case_id field found
    inside each file (not the filename)."""
    labels = json.loads(LABELS_PATH.read_text())
    active_labels = {k: v for k, v in labels.items() if not v.get("retired")}

    by_case_id: dict[str, str] = {}
    for path in CASES_DIR.glob("*.json"):
        raw = path.read_text()
        case_id = json.loads(raw)["case_id"]
        by_case_id[case_id] = raw

    cases: dict[str, dict] = {}
    for case_id, label in active_labels.items():
        if case_id not in by_case_id:
            raise RuntimeError(f"label {case_id} has no matching case file under {CASES_DIR}")
        cases[case_id] = {"case_json": by_case_id[case_id], "expected": label["expected"], "source": label.get("source")}
    return cases


def build_split(cases: dict[str, dict]) -> tuple[list[dspy.Example], list[dspy.Example]]:
    """Returns (train_examples, expert_eval_examples). train = the 8 non
    expert-labeled active cases; expert_eval = the 4 expert-labeled cases
    (CASE-101, 102, 106, 108)."""
    train, expert_eval = [], []
    for case_id, rec in cases.items():
        ex = dspy.Example(
            case_json=rec["case_json"],
            decision=rec["expected"],
        ).with_inputs("case_json")
        ex.case_id = case_id  # for reporting only, not part of the input/label
        if case_id in EXPERT_EVAL_IDS:
            expert_eval.append(ex)
        else:
            train.append(ex)
    return train, expert_eval


class AccountReviewSignature(dspy.Signature):
    """You are a risk-operations reviewer for flagged merchant accounts.
    Decide each case under the account-review decisioning policy below.

    ACCOUNT REVIEW DECISIONING POLICY (Risk Operations)

    Every flagged account is resolved as Approve (released), Hold (unresolved,
    funds remain held pending a document, verification, or decision), or
    Reject (blocked or closed). A corroborated problem warrants a Reject; a
    real but unresolved question warrants a Hold; absent either, the account
    is Approved.

    Weighing and proportionality: signals are weighed against exposure and
    track record, not applied mechanically, and the response is proportionate
    to what is at stake. A minor anomaly, or an immaterial amount, on an
    otherwise sound and well-established account does not warrant holding it;
    the same signal against a large exposure, or against a new account with
    little history to stand on, may. A long, consistent, verified history is
    mitigating; a new account has not yet earned that benefit of the doubt.
    No single small factor need be decisive, yet several unexplained concerns
    together can be enough to treat an account as unresolved. Some level of
    disputes, declines, and returns is normal; what matters is deviation from
    what the account's own history and profile would lead us to expect. Where
    genuine doubt remains and money is exposed, holding is preferred to
    releasing.

    Sanctions and watchlist: sanctions exposure carries zero tolerance, a
    genuine sanctions match is disqualifying. Watchlist screening is
    name-based and routinely produces false positives; a hit that does not
    hold up as the same individual is not, in itself, a concern.

    Account linkage: a genuine connection to known fraud, one that ties the
    same party to a bad account, is a serious concern. Incidental overlaps
    that do not establish common control are not, and neither is a connection
    to the holder's own accounts in good standing.

    Transaction activity: activity is judged on pattern, not volume.
    Systematic testing of payment credentials, and the rapid build-up and
    extraction of funds to an unestablished destination (a bust-out), are
    fraud; in a bust-out the loss is realised when the funds leave, so it does
    not depend on chargebacks to confirm it. Ordinary sales, however large or
    fast-growing, are not a concern.

    Identity, ownership, and funds at risk: where the party, or their control
    of the account, cannot presently be established and money is exposed, the
    risk is unresolved rather than confirmed.

    Confirmed history: a confirmed, adjudicated problem against the same
    party is disqualifying. A problem is only confirmed when a real prior
    determination stands behind it; a flag with nothing substantiating it, or
    one that conflicts with the record, is a data-quality question, not a
    confirmed problem.

    Evidence: conflicting sources are weighed on their merits. An account
    holder's own account of events is not evidence on its own.
    """

    case_json: str = dspy.InputField(desc="the full flagged-account case as raw JSON text")
    decision: str = dspy.OutputField(desc="exactly one of: APPROVE, HOLD, REJECT")
    reasoning: str = dspy.OutputField(desc="cite the specific fields and values that drove the decision")


def build_program() -> dspy.Module:
    return dspy.Predict(AccountReviewSignature)


def decision_exact_match(example: dspy.Example, prediction, trace=None) -> bool:
    """Metric: exact match on decision vs expected label. A prediction whose
    decision field is missing or outside {APPROVE, HOLD, REJECT} counts as
    incorrect, never as an exception (boundary-contracts: no silent failure)."""
    predicted = getattr(prediction, "decision", None)
    if predicted is None:
        return False
    predicted = str(predicted).strip().upper()
    if predicted not in VALID_DECISIONS:
        return False
    return predicted == example.decision


def configure_lm(api_key: str) -> dspy.LM:
    lm = dspy.LM(
        "gemini/gemini-2.5-flash",
        api_key=api_key,
        temperature=0.2,
        max_tokens=4096,
    )
    dspy.configure(lm=lm)
    return lm
