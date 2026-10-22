#!/usr/bin/env python3
"""Score a model's answers on the eval set.

  target/release/examples/train_io model.gguf < train/data/eval.jsonl > train/data/eval_out/NAME.jsonl
  python3 -I train/eval.py train/data/eval_out/NAME.jsonl     # → train/data/eval_out/NAME.score.json

Metrics: JSON the app can parse, verdict accuracy (by kind, language, label),
citations that exist (source in range, quote really in that passage), the
flip test (does the verdict change when only the outlet or the political
side changes?), queries in the clip's language, and whether the first query
finds the claim's Wikipedia article (SerpApi, cached in data/serp_cache.json).
Wikipedia is only the eval's yardstick, because the passages come from it;
it is not a default source of the product.
"""
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import NEE, lang_of, norm  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
SERP_CACHE = DATA / "serp_cache.json"
MAX_NEW_SEARCHES = 110  # free plan: 250 a month


def parse(raw):
    """Like factcheck_core::parse_verdicts: the outer {...}, claim and verdict strings."""
    try:
        v = json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
        claims = v["claims"]
        assert isinstance(claims, list) and all(isinstance(c["claim"], str) and isinstance(c["verdict"], str) for c in claims)
        return claims
    except (ValueError, KeyError, TypeError, AssertionError):
        return None


def source_of(c):
    s = c.get("source")
    try:
        return int(str(s).strip("[] ")) if s is not None else None
    except ValueError:
        return None


def serp(query, cache, budget):
    if query not in cache:
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        key = (Path.home() / ".config/lapacho-factcheck/serpapi_key").read_text().strip()
        url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(
            {"engine": "google", "q": query, "num": 4, "api_key": key})
        with urllib.request.urlopen(url, timeout=60) as r:
            res = json.load(r)
        cache[query] = [{"title": o.get("title", ""), "link": o.get("link", "")} for o in res.get("organic_results", [])[:4]]
        SERP_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0))
    return cache[query]


def score(path):
    rows = [json.loads(l) for l in open(path)]
    acc = defaultdict(Counter)
    cites = Counter()
    by_base = defaultdict(list)
    for r in rows:
        claims = parse(r.get("verdict_raw", ""))
        r["pred"] = claims
        acc["json"][claims is not None] += 1
        if claims is not None:
            acc["claim_count"][len(claims) == len(r["gold"])] += 1
        for i, g in enumerate(r["gold"]):
            p = claims[i] if claims and i < len(claims) else {}
            ok = p.get("verdict") == g["verdict"]
            for k in ("all", f"kind:{r['kind']}", f"lang:{r['lang']}", f"gold:{g['verdict']}"):
                acc[k][ok] += 1
            acc["confusion"][f"{g['verdict']}→{p.get('verdict', 'missing')}"] += 1
            if p.get("verdict") in ("supported", "contradicted"):
                s = source_of(p)
                in_range = s is not None and 0 < s <= len(r["passages"])
                quoted = in_range and bool(p.get("quote")) and norm(p["quote"]) in norm(r["passages"][s - 1])
                cites["predicted_sure"] += 1
                cites["source_in_range"] += in_range
                cites["quote_in_that_passage"] += quoted
                cites["right_source"] += ok and s == g["source"]
        if r.get("base"):
            by_base[r["base"]].append(r)
    # Outlet flips: the base item is part of the group too.
    ids = {r["id"]: r for r in rows}
    flips = Counter()
    for base, group in by_base.items():
        if base in ids:
            group = [ids[base]] + group
        verdicts = {tuple(c.get("verdict") for c in (g["pred"] or [])) for g in group}
        kind = group[-1]["kind"]
        flips[f"{kind}:groups"] += 1
        flips[f"{kind}:flipped"] += len(verdicts) > 1

    # Queries: base items only (flips repeat the same clip).
    base_rows = [r for r in rows if r["kind"] not in ("flip_outlet", "flip_political")]
    q = Counter()
    cache = json.loads(SERP_CACHE.read_text()) if SERP_CACHE.exists() else {}
    budget = [MAX_NEW_SEARCHES]
    for r in base_rows:
        qs = r.get("queries", [])
        q["clips"] += 1
        q["has_1_to_3"] += 1 <= len(qs) <= 3
        q["n_queries"] += len(qs)
        langs = [lang_of(x) for x in qs]
        q[f"{r['lang']}_clips"] += 1
        q[f"{r['lang']}_clips_all_queries_in_lang"] += bool(qs) and all(l in (r["lang"], "?") for l in langs)
        page = r["gold"][0].get("page", "")
        if qs and page and not page.startswith("political-"):
            res = serp(qs[0], cache, budget)
            if res is None:
                q["search_skipped_quota"] += 1
                continue
            q["searched"] += 1
            hit = any("wikipedia.org" in o["link"] and norm(page.split(" (")[0]) in norm(o["title"]) for o in res)
            q["first_query_finds_article"] += hit

    def pct(c, k=True):
        n = sum(c.values())
        return round(100 * c[k] / n, 1) if n else None

    out = {
        "file": str(path),
        "items": len(rows),
        "json_valid_%": pct(acc["json"]),
        "claim_count_right_%": pct(acc["claim_count"]),
        "verdict_accuracy_%": {k: pct(v) for k, v in sorted(acc.items()) if k not in ("json", "claim_count", "confusion")},
        "confusion": dict(acc["confusion"].most_common()),
        "citations": dict(cites),
        "flip": dict(flips),
        "queries": dict(q),
        "secs": {k: round(sum(r.get(k, 0) for r in rows) / len(rows), 1) for k in ("queries_secs", "verdict_secs")},
        "searches_left_in_budget": budget[0],
    }
    Path(str(path).replace(".jsonl", ".score.json")).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    score(sys.argv[1])
