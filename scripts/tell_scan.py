#!/usr/bin/env python3
"""Deterministic floor for the humanizer audit.

Counts surface-level AI-writing tells per pattern, with line numbers, so a run
can never claim "zero hits" without evidence. It is a floor, not a verdict:
many tells (elegant variation, false ranges, significance inflation) need
judgment and are not scanned here. A clean scan means only "none of the
regex-detectable tells fired".

Usage:
    python tell_scan.py FILE [--json] [--max-lines N] [--voice-dir DIR]
                        [--stats] [--compare FILE2]
    python tell_scan.py - < text            (read stdin)

    --voice-dir DIR   read DIR/allow.json and skip the advisory tell ids it lists
                      (habits that belong to that author). Hard tells are never
                      skippable.
    --stats           also print style statistics per 1,000 words and a tell
                      density score. Advisory only; exit codes do not change.
    --compare FILE2   with --stats, print the same statistics for a second text
                      (the original, or a voice sample) side by side. Run it as
                      `tell_scan.py REWRITE --stats --compare ORIGINAL`.

Exit code: 0 if no hard tells fired, 1 if any hard tell fired, 2 on usage error.
Hard tells are the ones a rewrite must remove (dashes, chatbot artifacts,
curly quotes, emoji). Everything else is advisory and printed for review.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys

# (id, name, hard, regex). Ids follow SKILL.md section numbers.
WORDS_AI = (
    r"additionally|align(?:s|ed)? with|crucial|delve[sd]?|delving|emphasiz\w+|enduring|enhanc\w+|"
    r"foster\w*|garner\w*|interplay|intricac\w+|intricate|pivotal|showcas\w+|tapestry|testament|"
    r"underscor\w+|vibrant|seamless(?:ly)?|robust|leverag\w+|holistic|nuanced|realm|"
    r"meticulous(?:ly)?|navigat(?:e|es|ing) the|ever-evolving|game[- ]changer"
)
TELLS = [
    ("7", "AI vocabulary", False, re.compile(rf"\b(?:{WORDS_AI})\b", re.I)),
    ("8", "copula avoidance", False, re.compile(r"\b(?:serves as|stands as|boasts|represents a)\b", re.I)),
    ("9", "negative parallelism", False, re.compile(
        r"\bnot (?:only|just|merely|simply)\b[^.?!]{0,80}\bbut\b|\bit'?s not (?:just|merely|about)\b", re.I)),
    ("9b", "copula-flip negation", False, re.compile(
        r"\b(?:is|was|are|were)(?:n't| not)\b[^.?!\n]{1,80}[.;,]\s+(?:it|this|that|they)(?:'s| is| was| are)\b", re.I)),
    ("10", "rule of three (X, Y, and Z)", False, re.compile(
        r"\b\w+(?: \w+)?, \w+(?: \w+)?,? and \w+(?: \w+)?\b")),
    ("14", "em or en dash", True, re.compile("[" + chr(0x2013) + chr(0x2014) + "]")),
    ("15", "boldface", False, re.compile(r"\*\*[^*\n]+\*\*")),
    ("16", "inline-header list item", False, re.compile(r"^\s*(?:[-*]|\d+\.)\s+\*\*[^*]+\*\*\s*:", re.M)),
    ("18", "emoji", True, re.compile("[\U0001F300-\U0001FAFF☀-➿✅❌⭐]")),
    ("19", "curly quotes", True, re.compile("[“”‘’]")),
    ("20", "chatbot artifact", True, re.compile(
        r"\b(?:I hope this (?:helps|email finds you)|let me know if you(?:'d like| need| have)|"
        r"great question|certainly!|of course!|happy to help|feel free to)\b", re.I)),
    ("21", "knowledge-cutoff disclaimer", True, re.compile(
        r"\b(?:as of my (?:last|knowledge)|I don'?t have access to real-time|as an AI)\b", re.I)),
    ("23", "filler phrase", False, re.compile(
        r"\b(?:in order to|it is worth noting|it'?s worth noting|at the end of the day|"
        r"in today'?s (?:fast-paced|digital|modern)|when it comes to|the fact that)\b", re.I)),
    ("24", "stacked hedging", False, re.compile(
        r"\b(?:may|might|could) (?:potentially|possibly)\b|\b(?:arguably|perhaps)\b[^.]{0,40}\b(?:may|might)\b", re.I)),
    ("25", "generic positive conclusion", False, re.compile(
        r"\b(?:the future (?:looks|is) bright|exciting times|a (?:bright|promising) future|"
        r"moving forward|paving the way|stands ready)\b", re.I)),
    ("28", "signposting", False, re.compile(
        r"\b(?:let'?s (?:dive|break (?:it|this) down|take a (?:closer )?look)|here'?s (?:the thing|what|why|how)|"
        r"in conclusion|in summary|to summarize|without further ado)\b", re.I)),
    ("33", "rhetorical opener", False, re.compile(
        r"^(?:So,? |Ever wondered|Imagine |Picture this|The (?:truth|reality|answer)\??(?: is)?:)", re.I | re.M)),
    ("35", "intensifier adverb", False, re.compile(
        r"\b(?:quietly|genuinely|truly|deeply|incredibly|fundamentally|seamlessly|effortlessly|remarkably)\b", re.I)),
    ("36", "colon or question reveal", False, re.compile(
        r"\b(?:the (?:result|kicker|catch|twist|fix|answer|truth|problem|upshot)(?::|\?)|here'?s the (?:kicker|catch|twist):?)", re.I)),
    ("34", "unearned experience or statistic (verify against source)", False, re.compile(
        r"\b(?:I|we) (?:run|ran|built|have (?:seen|run|built|found)|'ve (?:seen|run|built|found)|found that|tested)\b|"
        r"\bin (?:my|our) experience\b|\b\d{1,3}(?:\.\d+)? ?(?:percent|%)", re.I)),
    # Section 39 (2026 tells)
    ("39a", "'Y rather than X' contrast framing", False, re.compile(r"\brather than\b", re.I)),
    ("39b", "vague 'associated with' linking", False, re.compile(
        r"\b(?:associated with|in connection with|in association with)\b", re.I)),
    ("39c", "primary-source identification phrasing", False, re.compile(
        r"\b(?:primary sources? (?:identif\w+|indicat\w+|confirm\w*|show\w*|suggest\w*|reveal\w*)|"
        r"according to (?:the )?(?:primary|original) sources?|identified (?:in|by) (?:the )?primary sources?|"
        r"(?:the )?primary source (?:is|was))\b", re.I)),
    ("39d", "source-availability disclaimer", False, re.compile(
        r"\b(?:I (?:could not|couldn'?t|was unable to|cannot|can'?t) (?:access|find|verify|locate|confirm)|"
        r"sources? (?:may be|might be|are|remain) (?:unavailable|limited|scarce|incomplete)|"
        r"(?:records?|documents?|information|details) (?:may|might) (?:be )?(?:unavailable|incomplete|limited)|"
        r"(?:limited|no) (?:publicly )?available (?:sources?|information|records?)|"
        r"not (?:readily|widely|publicly) available|as of my (?:training|latest))\b", re.I)),
]

# Era tags: current (2025-2026 models), fading (older or declining), historical
# (2022-2023 era, rare in new output). A judgment call: revisit each model generation.
ERA = {t: "fading" for t in ("2", "4", "6", "7", "18", "23", "25")}
ERA.update({t: "historical" for t in ("17", "19", "20", "21", "22")})
ERA_RANK = {"current": 0, "fading": 1, "historical": 2}


def era_of(tid: str) -> str:
    return ERA.get(tid, "current")


TITLE_CASE_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.M)
SMALL = {"a", "an", "the", "and", "or", "but", "of", "in", "on", "to", "for", "at", "by", "with", "vs", "is"}


def title_case_headings(text: str) -> list[int]:
    hits = []
    for m in TITLE_CASE_HEADING.finditer(text):
        words = [w for w in re.findall(r"[A-Za-z][\w'-]*", m.group(1))]
        content = [w for w in words[1:] if w.lower() not in SMALL]
        if len(content) >= 2 and all(w[0].isupper() for w in content):
            hits.append(text.count("\n", 0, m.start()) + 1)
    return hits


def conjunction_runs(text: str) -> list[tuple[int, str]]:
    """Paragraphs with 2 consecutive or 3+ total sentences opening And/But/So."""
    hits, line = [], 1
    for para in re.split(r"\n\s*\n", text):
        sents = re.split(r"(?<=[.!?])\s+", para.strip())
        flags = [bool(re.match(r"(?:And|But|So)\b", x)) for x in sents]
        consec = any(a and b for a, b in zip(flags, flags[1:]))
        if consec or sum(flags) >= 3:
            hits.append((line, f"{sum(flags)} of {len(sents)} sentences"))
        line += para.count("\n") + 2
    return hits


def paren_density(text: str) -> list[tuple[int, str]]:
    """Paragraphs with more than one parenthetical aside (section 38)."""
    hits, line = [], 1
    for para in re.split(r"\n\s*\n", text):
        n = len(re.findall(r"\([^()\n]{3,}\)", para))
        if n > 1:
            hits.append((line, f"{n} parentheticals"))
        line += para.count("\n") + 2
    return hits


def staccato_runs(text: str) -> list[tuple[int, str]]:
    """Runs of 3+ consecutive sentences of five words or fewer (section 31)."""
    hits, line = [], 1
    for para in re.split(r"\n\s*\n", text):
        if not para.lstrip().startswith(("#", "-", "*", ">")):
            sents = [s for s in re.split(r"(?<=[.!?])\s+", para.strip()) if s]
            run = best = 0
            for s in sents:
                run = run + 1 if len(s.split()) <= 5 else 0
                best = max(best, run)
            if best >= 3:
                hits.append((line, f"{best} short sentences in a row"))
        line += para.count("\n") + 2
    return hits


def sentence_stats(text: str) -> dict:
    body = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)  # YAML frontmatter
    body = re.sub(r"(?m)^#.*$", "", body)  # headings
    sents = [s for s in re.split(r"(?<=[.!?])\s+", body) if len(s.split()) >= 2]
    lens = [len(s.split()) for s in sents]
    if not lens:
        return {"sentences": 0}
    return {
        "sentences": len(lens),
        "mean_words": round(statistics.mean(lens), 1),
        "stdev_words": round(statistics.pstdev(lens), 1),
        "short_le_8": sum(1 for n in lens if n <= 8),
        "long_ge_30": sum(1 for n in lens if n >= 30),
    }


def scan(text: str, allow: set[str] | None = None) -> dict:
    allow = allow or set()
    lines = text.splitlines()
    out = []
    for tid, name, hard, rx in TELLS:
        if tid in allow and not hard:
            continue
        hits = []
        for i, line in enumerate(lines, 1):
            for m in rx.finditer(line):
                hits.append({"line": i, "match": m.group(0)[:80]})
        out.append({"id": tid, "name": name, "hard": hard, "count": len(hits), "hits": hits})
    para_tells = [("37", "And/But/So opener run", conjunction_runs),
                  ("38", "parenthetical density", paren_density),
                  ("31", "staccato run of short sentences", staccato_runs)]
    for tid, name, fn in para_tells:
        if tid in allow:
            continue
        runs = fn(text)
        out.append({"id": tid, "name": name, "hard": False, "count": len(runs),
                    "hits": [{"line": n, "match": m} for n, m in runs]})
    if "17" not in allow:
        tc = title_case_headings(text)
        out.append({"id": "17", "name": "title-case heading", "hard": False, "count": len(tc),
                    "hits": [{"line": n, "match": lines[n - 1][:80]} for n in tc]})
    for t in out:
        t["era"] = era_of(t["id"])
    out.sort(key=lambda t: (not t["hard"], ERA_RANK[t["era"]], -t["count"]))
    return {"tells": out, "stats": sentence_stats(text),
            "hard_total": sum(t["count"] for t in out if t["hard"]),
            "advisory_total": sum(t["count"] for t in out if not t["hard"])}


# ---- style statistics (--stats) -------------------------------------------

LY_EXCLUDE = {"only", "family", "early", "reply", "apply", "supply", "july", "italy", "daily", "likely",
              "really", "rely", "ally", "belly", "bully", "fly", "ugly", "holy", "lily", "jelly", "assembly"}
NOMINAL_RX = re.compile(r"(?:tions?|ments?|ness(?:es)?|it(?:y|ies))$")
FIRST_PERSON = {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves",
                "i'm", "i've", "i'll", "i'd", "we're", "we've", "we'll", "we'd"}
CONTRACTION_RX = re.compile(
    r"\b\w+(?:n't|'re|'ve|'ll|'d|'m)\b|\b(?:it|that|he|she|there|what|let|here|who)'s\b", re.I)


def _rate(n: float, words: int) -> float:
    return round(n * 1000.0 / words, 1) if words else 0.0


def mattr(tokens: list[str], window: int = 50) -> float:
    if not tokens:
        return 0.0
    if len(tokens) <= window:
        return round(len(set(tokens)) / len(tokens), 3)
    vals = [len(set(tokens[i:i + window])) / window for i in range(len(tokens) - window + 1)]
    return round(sum(vals) / len(vals), 3)


def text_stats(text: str) -> dict:
    """Style statistics per 1,000 words. Advisory: a prompt for judgment, not a verdict."""
    body = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    norm = body.replace("’", "'").replace("‘", "'")
    toks = [w.lower().strip("'") for w in re.findall(r"[A-Za-z][A-Za-z']*", norm)]
    n = len(toks)
    paras = [p for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    prose = [p for p in paras if not p.lstrip().startswith("#")]
    plen = [len(p.split()) for p in prose]
    one_line = sum(1 for p in prose
                   if "\n" not in p.strip() and not re.match(r"\s*(?:[-*+•]|\d+[.)])\s", p))
    return {
        "words": n,
        "long_words_7plus": _rate(sum(1 for w in toks if len(w) >= 7), n),
        "nominalisations": _rate(sum(1 for w in toks if len(w) >= 6 and NOMINAL_RX.search(w)), n),
        "ly_adverbs": _rate(sum(1 for w in toks if len(w) >= 5 and w.endswith("ly") and w not in LY_EXCLUDE), n),
        "commas": _rate(norm.count(","), n),
        "contractions": _rate(len(CONTRACTION_RX.findall(norm)), n),
        "first_person": _rate(sum(1 for w in toks if w in FIRST_PERSON), n),
        "mattr_50": mattr(toks),
        "paragraphs": len(prose),
        "paragraph_words_mean": round(statistics.mean(plen), 1) if plen else 0.0,
        "paragraph_words_stdev": round(statistics.pstdev(plen), 1) if plen else 0.0,
        "one_line_paragraphs": one_line,
        "bullets": _rate(len(re.findall(r"(?m)^\s*(?:[-*+•]|\d+[.)])\s", body)), n),
        "headings": _rate(len(re.findall(r"(?m)^#{1,6}\s", body)), n),
        "bold": _rate(len(re.findall(r"\*\*[^*\n]+\*\*", body)), n),
    }


def tell_density(res: dict, words: int) -> float:
    """Weighted tells per 1,000 words. Hard tells weigh 3. An id that fires more than
    once is a repeated tic: each extra hit adds 25 percent (capped at four extras)."""
    total = 0.0
    for t in res["tells"]:
        c = t["count"]
        if not c:
            continue
        weight = 3.0 if t["hard"] else 1.0
        total += weight * c * (1 + 0.25 * min(c - 1, 4))
    return _rate(total, words)


def full_stats(text: str, allow: set[str] | None = None) -> dict:
    st = text_stats(text)
    st["tell_density"] = tell_density(scan(text, allow), st["words"])
    return st


def print_stats(a: dict, b: dict | None) -> None:
    print("--- stats per 1,000 words (advisory) ---")
    head = f"{'metric':<24}{'file':>10}" + (f"{'compare':>10}{'change':>9}" if b else "")
    print(head)
    for k, v in a.items():
        row = f"{k:<24}{v:>10}"
        if b is not None:
            w = b[k]
            if w:
                row += f"{w:>10}{(v - w) / w * 100:>+8.0f}%"
            else:
                row += f"{w:>10}{'n/a':>9}"
        print(row)
    if b and a["commas"] > 0 and a["commas"] > b["commas"] * 1.25:
        print("check: comma rate rose by more than 25 percent over the compare text; trim commas (SKILL.md section 14)")


def load_allow(voice_dir: str) -> set[str]:
    import os
    path = os.path.join(voice_dir, "allow.json")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    raw = data.get("allow", []) if isinstance(data, dict) else data
    ids = set(raw) if isinstance(raw, (list, dict)) else set()
    hard = {t[0] for t in TELLS if t[2]}
    blocked = {i for i in ids if i in hard}
    if blocked:
        print(f"note: hard tells cannot be allowlisted, ignoring {sorted(blocked)}", file=sys.stderr)
    return {str(i) for i in ids} - hard


def _read(src: str) -> str:
    if src == "-":
        return sys.stdin.read()
    with open(src, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("file", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-lines", type=int, default=6)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--compare")
    ap.add_argument("--voice-dir")
    try:
        ns = ap.parse_args(argv)
    except SystemExit:
        print(__doc__, file=sys.stderr)
        return 2
    if not ns.file or (ns.compare and not ns.stats):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        text = _read(ns.file)
        other = _read(ns.compare) if ns.compare else None
        allow = load_allow(ns.voice_dir) if ns.voice_dir else set()
    except (OSError, ValueError) as exc:
        print(f"tell_scan: {exc}", file=sys.stderr)
        return 2
    res = scan(text, allow)
    stats_a = full_stats(text, allow) if ns.stats else None
    stats_b = full_stats(other, allow) if other is not None else None
    if ns.json:
        if allow:
            res["allowlisted"] = sorted(allow)
        if stats_a is not None:
            res["text_stats"] = stats_a
        if stats_b is not None:
            res["compare_stats"] = stats_b
        print(json.dumps(res, indent=1))
    else:
        for t in res["tells"]:
            if not t["count"]:
                continue
            tag = "HARD" if t["hard"] else "check"
            print(f"[{tag}] {t['id']:>3} {t['name']} ({t['era']}): {t['count']}")
            for h in t["hits"][:ns.max_lines]:
                print(f"        L{h['line']}: {h['match']}")
            if t["count"] > ns.max_lines:
                print(f"        ... {t['count'] - ns.max_lines} more")
        print(f"hard={res['hard_total']} advisory={res['advisory_total']} stats={res['stats']}")
        if allow:
            print(f"allowlisted for this voice: {sorted(allow)}")
        print("note: scan is a floor; judgment tells (significance inflation, synonym cycling, false ranges) are not scanned")
        if stats_a is not None:
            print_stats(stats_a, stats_b)
    return 1 if res["hard_total"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
