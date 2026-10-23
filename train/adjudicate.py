#!/usr/bin/env python3
"""Apply data/eval_adjudication.json to the eval.

  python3 -I train/adjudicate.py                        # → data/eval_adjudicated.jsonl
  python3 -I train/adjudicate.py data/eval_out/NAME.jsonl   # rescore a finished run → NAME.adjudicated.score.json

The original expected verdicts stay in `gold_original`. Dropped items and the
four rewritten political passages are left out of a rescore: the old run saw
the old passages.
"""
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval import score  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
ADJ = json.loads((DATA / "eval_adjudication.json").read_text())


def base_id(i):
    m = re.match(r"(e\d+)", i)  # e033-CNN follows e033
    return m.group(1) if m else i


def apply(row, rescoring=False):
    """The adjudicated row, or None if it's dropped (or rewritten, when rescoring)."""
    i = row["id"]
    if base_id(i) in ADJ["drop"] or (rescoring and i in ADJ["rewrite"]):
        return None
    row = copy.deepcopy(row)
    row["gold_original"] = copy.deepcopy(row["gold"])
    c = ADJ["change"].get(base_id(i))
    if c:
        g = row["gold"][c["claim"]]
        g["verdict"], g["source"] = c["verdict"], c["source"]
        row["adjudication"] = {"reason": c["reason"], "note": c["note"]}
    w = ADJ["rewrite"].get(i)
    if w and not rescoring:
        row["passages"][w["source"] - 1] = w["passage"]
        row["adjudication"] = {"reason": "rewritten-passage", "note": ADJ["rewrite"]["_why"]}
    return row


if __name__ == "__main__":
    if len(sys.argv) == 1:
        rows = [r for r in (apply(json.loads(l)) for l in open(DATA / "eval.jsonl")) if r]
        (DATA / "eval_adjudicated.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        print(len(rows), "items in eval_adjudicated.jsonl")
    else:
        src = Path(sys.argv[1])
        rows = [r for r in (apply(json.loads(l), rescoring=True) for l in open(src)) if r]
        out = src.with_name(src.stem + ".adjudicated.jsonl")
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        score(out)
