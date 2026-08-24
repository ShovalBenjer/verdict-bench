#!/usr/bin/env python3
"""Bank human adjudications from the playground's contested queue.

The static UI cannot write files, so the loop closes here: the queue's
summary screen offers "copy adjudication JSON"; paste it into this tool's
stdin and each call lands as one row in state/annotations.jsonl with the
paste timestamp. Rows are append-only; conflicting adjudications for the
same case are kept (they ARE the disagreement data), and the label file is
never auto-edited: promoting an adjudicated answer into data/labels.json
stays a human edit with the annotation rows as its evidence.

Run: python3 tools/ingest_annotations.py < paste.json
  or: python3 tools/ingest_annotations.py   (paste, then ctrl-d)
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "state" / "annotations.jsonl"
DECISIONS = ("APPROVE", "HOLD", "REJECT")


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print("nothing on stdin; paste the queue's adjudication JSON")
        return 1
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"not valid JSON: {e}")
        return 1
    calls = payload.get("calls", [])
    if not isinstance(calls, list) or not calls:
        print("payload has no calls[]")
        return 1
    stamp = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    banked = 0
    with OUT.open("a") as f:
        for c in calls:
            if c.get("your_call") not in DECISIONS or not str(c.get("case_id", "")).startswith("CASE-"):
                print(f"skipped malformed call: {c!r}")
                continue
            f.write(json.dumps({
                "case_id": c["case_id"], "your_call": c["your_call"],
                "model": c.get("model"), "written_label": c.get("written_label"),
                "ingested_at": stamp}) + "\n")
            banked += 1
    print(f"banked {banked} adjudication(s) into {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
