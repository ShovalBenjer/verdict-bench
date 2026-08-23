"""One-off smoke test: confirm dspy.LM("gemini/gemini-2.5-flash", ...) returns a
parseable response before building the full eval loop. Not part of the arm's
deliverable; run manually, then delete or ignore."""
from __future__ import annotations

import os

import dspy


def read_env_key(name: str) -> str:
    v = os.environ.get(name, "")
    if v:
        return v
    env_path = os.path.expanduser("~/.env")
    with open(env_path) as fh:
        for line in fh:
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError(f"missing credential {name}")


def main() -> None:
    key = read_env_key("GEMINI_API_KEY")
    lm = dspy.LM(
        "gemini/gemini-2.5-flash",
        api_key=key,
        temperature=0.2,
        max_tokens=2048,
    )
    dspy.configure(lm=lm)

    class Sig(dspy.Signature):
        """Decide APPROVE, HOLD, or REJECT for a flagged account case."""

        case_json: str = dspy.InputField()
        decision: str = dspy.OutputField(desc="one of APPROVE, HOLD, REJECT")
        reasoning: str = dspy.OutputField()

    predictor = dspy.Predict(Sig)
    result = predictor(case_json='{"case_id": "SMOKE-1", "flag_reason": "TEST"}')
    print("decision:", repr(result.decision))
    print("reasoning:", repr(result.reasoning)[:200])
    print("history entries:", len(lm.history))
    print("last message shape:", list(lm.history[-1].keys()))


if __name__ == "__main__":
    main()
