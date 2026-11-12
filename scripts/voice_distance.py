#!/usr/bin/env python3
"""Advisory voice-distance check: did the rewrite move closer to the voice sample?

Character 3 to 5-gram TF-IDF vectors (sublinear term frequency, smoothed IDF
over the texts given) and cosine distance to the voice sample. Lower distance
means closer in surface style: spelling habits, function words, punctuation,
contractions. It does not read meaning and is a hint, not a verdict. Short
texts (under about 150 words) give noisy numbers.

Usage:
    python voice_distance.py --voice SAMPLE --rewrite REWRITE [--original ORIGINAL] [--json]

Exit code: 0 on a successful run (the result is advisory, never a failure),
2 on usage error or unreadable file. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter


def grams(text: str, lo: int = 3, hi: int = 5) -> Counter:
    t = re.sub(r"\s+", " ", text.lower().replace("’", "'")).strip()
    c: Counter = Counter()
    for n in range(lo, hi + 1):
        for i in range(len(t) - n + 1):
            c[t[i:i + n]] += 1
    return c


def vectors(texts: list[str]) -> list[dict[str, float]]:
    counts = [grams(t) for t in texts]
    df: Counter = Counter()
    for c in counts:
        df.update(c.keys())
    n = len(texts)
    out = []
    for c in counts:
        out.append({g: (1 + math.log(f)) * (math.log((1 + n) / (1 + df[g])) + 1) for g, f in c.items()})
    return out


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    dot = sum(v * b.get(g, 0.0) for g, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def distances(voice: str, rewrite: str, original: str | None = None) -> dict:
    texts = [voice, rewrite] + ([original] if original is not None else [])
    vecs = vectors(texts)
    res = {"rewrite_distance": round(1 - cosine(vecs[0], vecs[1]), 4)}
    if original is not None:
        res["original_distance"] = round(1 - cosine(vecs[0], vecs[2]), 4)
        res["moved_closer"] = res["rewrite_distance"] < res["original_distance"]
        res["change"] = round(res["rewrite_distance"] - res["original_distance"], 4)
    res["voice_words"] = len(voice.split())
    res["short_sample_warning"] = len(voice.split()) < 150
    return res


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--voice")
    ap.add_argument("--rewrite")
    ap.add_argument("--original")
    ap.add_argument("--json", action="store_true")
    try:
        ns = ap.parse_args(argv)
    except SystemExit:
        print(__doc__, file=sys.stderr)
        return 2
    if not ns.voice or not ns.rewrite:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        res = distances(_read(ns.voice), _read(ns.rewrite), _read(ns.original) if ns.original else None)
    except OSError as exc:
        print(f"voice_distance: {exc}", file=sys.stderr)
        return 2
    if ns.json:
        print(json.dumps(res, indent=1))
        return 0
    if "original_distance" in res:
        print(f"original distance: {res['original_distance']}")
    print(f"rewrite distance:  {res['rewrite_distance']}")
    if "moved_closer" in res:
        verdict = "closer to" if res["moved_closer"] else "NOT closer to"
        print(f"the rewrite is {verdict} the voice sample (change {res['change']:+})")
    if res["short_sample_warning"]:
        print(f"note: voice sample is only {res['voice_words']} words; treat the numbers as noise")
    print("advisory only: surface style, not meaning")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
