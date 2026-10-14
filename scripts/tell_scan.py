#!/usr/bin/env python3
"""Deterministic floor for the humanizer audit.

Counts surface-level AI-writing tells per pattern, with line numbers, so a run
can never claim "zero hits" without evidence. It is a floor, not a verdict:
many tells (elegant variation, false ranges, significance inflation) need
judgment and are not scanned here. A clean scan means only "none of the
regex-detectable tells fired".

Usage:
    python tell_scan.py FILE [--json] [--max-lines N]
    python tell_scan.py - < text            (read stdin)

Exit code: 0 if no hard tells fired, 1 if any hard tell fired, 2 on usage error.
Hard tells are the ones a rewrite must remove (dashes, chatbot artifacts,
curly quotes, emoji). Everything else is advisory and printed for review.
Stdlib only.
"""

from __future__ import annotations

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
]

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


def scan(text: str) -> dict:
    lines = text.splitlines()
    out = []
    for tid, name, hard, rx in TELLS:
        hits = []
        for i, line in enumerate(lines, 1):
            for m in rx.finditer(line):
                hits.append({"line": i, "match": m.group(0)[:80]})
        out.append({"id": tid, "name": name, "hard": hard, "count": len(hits), "hits": hits})
    runs = conjunction_runs(text)
    out.append({"id": "37", "name": "And/But/So opener run", "hard": False, "count": len(runs),
                "hits": [{"line": n, "match": m} for n, m in runs]})
    tc = title_case_headings(text)
    out.append({"id": "17", "name": "title-case heading", "hard": False, "count": len(tc),
                "hits": [{"line": n, "match": lines[n - 1][:80]} for n in tc]})
    out.sort(key=lambda t: (not t["hard"], -t["count"]))
    return {"tells": out, "stats": sentence_stats(text),
            "hard_total": sum(t["count"] for t in out if t["hard"]),
            "advisory_total": sum(t["count"] for t in out if not t["hard"])}


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    max_lines = 6
    if "--max-lines" in argv:
        max_lines = int(argv[argv.index("--max-lines") + 1])
        args = [a for a in args if a != str(max_lines)]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    src = args[0]
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8", errors="replace").read()
    res = scan(text)
    if as_json:
        print(json.dumps(res, indent=1))
    else:
        for t in res["tells"]:
            if not t["count"]:
                continue
            tag = "HARD" if t["hard"] else "check"
            print(f"[{tag}] {t['id']:>3} {t['name']}: {t['count']}")
            for h in t["hits"][:max_lines]:
                print(f"        L{h['line']}: {h['match']}")
            if t["count"] > max_lines:
                print(f"        ... {t['count'] - max_lines} more")
        print(f"hard={res['hard_total']} advisory={res['advisory_total']} stats={res['stats']}")
        print("note: scan is a floor; judgment tells (significance inflation, synonym cycling, false ranges) are not scanned")
    return 1 if res["hard_total"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
