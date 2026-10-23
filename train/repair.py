#!/usr/bin/env python3
"""Clean the training rows for the strict rule: judge only from the passages shown.

  LLAMA_KEY=... python3 -I train/repair.py        # data/train.jsonl → data/train_repaired.jsonl

A Wikipedia sentence that says "The film was heavily panned" is labelled
supported for "Mutiny on the Bounty is a film" because the dataset knows the
page title; the model never sees it. For each one-claim verdict row whose cited
passage doesn't name the claim's subject:
  - the teacher rewrites the passage to name it → same verdict (if its quote still holds),
  - the original passage stays, now labelled not_enough_evidence,
  - the noisy original row is dropped.
Then two more kinds of not_enough_evidence (the passage is about someone else
with the same attribute), and a search-snippet look (a date in front, "..."
behind) on some passages. Nothing outside the cited passage changes.
"""
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import DATA, NEE, answer, json_obj, pmap, teacher  # noqa: E402

N_SWAP = 300
SNIPPET = 0.3
rng = random.Random(26)
STOP = {"the", "this", "that", "los", "las", "una", "uno", "del", "con", "por", "para", "its", "his", "her", "they", "there", "when", "after", "one"}
PASSAGE = re.compile(r"^\[(\d+)\] (.*)$", re.M)


def caps(t):
    return {w.lower() for w in re.findall(r"\b[A-ZÁÉÍÓÚÑ][\w'’-]{2,}\b", t)} - STOP


def parse(row):
    """(claim, {n: passage}, claims in the answer) of a verdict row, or None."""
    u = row["messages"][0]["content"]
    if "Passages:" not in u:
        return None
    try:
        out = json.loads(row["messages"][-1]["content"])["claims"]
    except (ValueError, KeyError):
        return None
    return {int(n): p for n, p in PASSAGE.findall(u.split("Passages:")[1])}, out


def swap_passage(row, n, old, new):
    r = json.loads(json.dumps(row))
    r["messages"][0]["content"] = r["messages"][0]["content"].replace(f"[{n}] {old}", f"[{n}] {new}", 1)
    return r


def with_answer(row, claim):
    r = json.loads(json.dumps(row))
    r["messages"][-1]["content"] = answer([claim])
    return r


def restore_subject(claim, passage, lang):
    out = json_obj(teacher(
        "The passage below is one sentence taken out of a longer text, so it may refer to its subject "
        "with a pronoun or a generic noun ('The film', 'It', 'Tiene'). Rewrite it so it names the subject "
        "explicitly, using the name the claim uses. Change nothing else: no new facts, same language. "
        'Answer with JSON only: {"passage": "...", "quote": "the exact words of the new passage that settle '
        'the claim"}\n\nClaim: ' + claim + "\nPassage: " + passage, max_tokens=300, json_mode=True))
    if not out or not isinstance(out.get("passage"), str) or not isinstance(out.get("quote"), str):
        return None
    p, q = out["passage"].strip(), out["quote"].strip()
    return (p, q) if q and q in p and caps(claim) & caps(p) else None


def other_entity(claim, passage, lang):
    """A passage about someone else with the same attribute: it can't settle the claim."""
    p = teacher(
        "Rewrite the passage so it is about a different, similar entity (another person, place, work or "
        "organization) with the same kind of fact, so that it says nothing about the claim's subject. Keep "
        "the style, the length and the language. Do not mention the claim's subject. Answer with the passage "
        "only.\n\nClaim: " + claim + "\nPassage: " + passage, max_tokens=200)
    p = (p or "").strip().strip('"')
    return p if p and not (caps(claim) & caps(p)) else None


def snippet(p, lang):
    months = ("ene feb mar abr may jun jul ago sep oct nov dic" if lang == "es" else "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec").split()
    d = f"{rng.randint(1, 28)} {months[rng.randrange(12)]} {rng.randint(2012, 2025)}" if lang == "es" else \
        f"{months[rng.randrange(12)]} {rng.randint(1, 28)}, {rng.randint(2012, 2025)}"
    return (f"{d} — " if rng.random() < 0.7 else "") + p + (" ..." if rng.random() < 0.5 else "")


def main():
    rows = [json.loads(l) for l in open(DATA / "train.jsonl")]
    stat = Counter()
    jobs, plain = [], []  # headless rows to repair; everything else
    for row in rows:
        pr = parse(row) if row.get("kind") in ("single", "es_claim_en_passages") else None
        if pr and len(pr[1]) == 1 and pr[1][0]["verdict"] != NEE and pr[1][0].get("source") in pr[0]:
            c = pr[1][0]
            if not caps(c["claim"]) & caps(pr[0][c["source"]]) and caps(c["claim"]):
                jobs.append((row, pr[0], c))
                continue
        plain.append(row)
    print(len(jobs), "headless rows to repair", file=sys.stderr)
    fixed = pmap(lambda j: restore_subject(j[2]["claim"], j[1][j[2]["source"]], j[0]["lang"]), jobs, "repair")
    out = list(plain)
    for (row, ps, c), f in zip(jobs, fixed):
        n = c["source"]
        out.append(with_answer(row, dict(c, verdict=NEE, source=None, quote="")))  # original passage → no evidence
        stat["nee_from_headless"] += 1
        if f:
            out.append(with_answer(swap_passage(row, n, ps[n], f[0]), dict(c, quote=f[1])))
            stat["repaired_kept_verdict"] += 1
        else:
            stat["repair_failed"] += 1
    # Same attribute, other entity → not enough evidence.
    pool = [(r, *parse(r)) for r in plain if r.get("kind") == "single" and parse(r) and len(parse(r)[1]) == 1
            and parse(r)[1][0]["verdict"] == "supported" and parse(r)[1][0].get("source") in parse(r)[0]]
    rng.shuffle(pool)
    pool = pool[:N_SWAP]
    swaps = pmap(lambda x: other_entity(x[2][0]["claim"], x[1][x[2][0]["source"]], x[0]["lang"]), pool, "swap")
    for (row, ps, cl), p in zip(pool, swaps):
        if p:
            c = cl[0]
            out.append(with_answer(swap_passage(row, c["source"], ps[c["source"]], p), dict(c, verdict=NEE, source=None, quote="")))
            stat["nee_other_entity"] += 1
    # Search-snippet look on some cited passages (the quote stays inside the passage).
    for i, row in enumerate(out):
        pr = parse(row) if row.get("kind") in ("single", "es_claim_en_passages") else None
        if pr and len(pr[1]) == 1 and pr[1][0].get("source") in pr[0] and rng.random() < SNIPPET:
            n = pr[1][0]["source"]
            out[i] = swap_passage(row, n, pr[0][n], snippet(pr[0][n], row["lang"]))
            stat["snippet_look"] += 1
    rng.shuffle(out)
    (DATA / "train_repaired.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    verdicts = Counter(c["verdict"] for r in out if (p := parse(r)) for c in p[1])
    print(json.dumps({"rows_in": len(rows), "rows_out": len(out), **stat, "verdicts": dict(verdicts)}, indent=1))


if __name__ == "__main__":
    main()
