#!/usr/bin/env python3
"""Compare the checkable facts of a source text and its rewrite.

A rewrite may change wording, never the facts. This script extracts the items
a reader would check (numbers with units and currency, dates, capitalised
names, quoted spans, URLs, emails, form ids, statute and regulation cites)
from both texts and reports what was added, dropped or changed. Values are
compared after normalising reformatting that keeps the value: 1,000 vs 1000,
Nov 3 vs November 3, 50% vs 50 percent, Art. 133 vs Article 133.

Usage:
    python unit_diff.py SOURCE REWRITE [--json]
    (use - for one of the two files to read stdin)

Exit code: 0 no difference, 1 at least one mismatch, 2 usage error.
Comparison is by presence, not count. Spelled-out numbers ("three") are not
converted. Name detection is heuristic: confirm each reported name by eye.
Stdlib only.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from decimal import Decimal

KINDS = ("url", "email", "quote", "cite", "form", "date", "number", "name")

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MONTH_RX = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
            r"Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
DAY_RX = r"(?P<d>\d{1,2})(?:st|nd|rd|th)?"

URL_RX = re.compile(r"(?:https?://|www\.)[^\s<>\"')\]]+", re.I)
EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
QUOTE_RX = re.compile(r'"([^"\n]{2,}?)"')

CITE_RXS = [
    re.compile(r"\b\d+\s*(?:U\.?\s?S\.?\s?C\.?|C\.?\s?F\.?\s?R\.?|Stat\.)\s*(?:§{1,2}\s*)?\d[\w.-]*(?:\([\w]+\))*", re.I),
    re.compile(r"\b\d+\s+(?:U\.S\.|F\.\d(?:d|th)|F\. ?Supp\.(?: ?\d(?:d|th))?|S\. ?Ct\.|M\.J\.|C\.M\.R\.)\s+\d+"),
    re.compile(r"(?:\b(?:Art(?:icle)?s?|Sec(?:tion)?s?|Para(?:graph)?|Rule|R\.?C\.?M\.?)\.?|§{1,2})\s*\d+[\w.-]*(?:\([\w]+\))*", re.I),
]
FORM_RX = re.compile(r"\b(?P<pre>VA|DD|SF|IRS|OMB|FAA|Form|Schedule)(?:\s+Form)?[\s-]+(?P<id>(?:[A-Z]-?)?\d[\w-]*)")

DATE_RXS = [
    re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b"),
    re.compile(r"\b(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{2,4})\b"),
    re.compile(rf"\b(?P<mon>{MONTH_RX})\.?\s+{DAY_RX}\b(?:,?\s+(?P<y>\d{{4}})\b)?"),
    re.compile(rf"\b{DAY_RX}\s+(?P<mon>{MONTH_RX})\.?(?:,?\s+(?P<y>\d{{4}})\b)?"),
    re.compile(rf"\b(?P<mon>{MONTH_RX})\.?,?\s+(?P<y>\d{{4}})\b"),
]

UNITS = (r"percent|per cent|thousand|million|billion|trillion|bn|mg|kg|g|lbs?|oz|miles?|mi|km|ft|feet|"
         r"hours?|hrs?|minutes?|mins?|seconds?|secs?|days?|weeks?|months?|years?|yrs?|gb|mb|tb|ms|usd|dollars?")
NUM_RX = re.compile(
    r"(?<![\w.])(?P<cur>[$€£])?\s?(?P<val>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<dec>\d+))?"
    r"(?:(?P<att>%|(?-i:[kKMB])(?![A-Za-z\d]))|\s?(?P<unit>(?:" + UNITS + r")\b))?(?![\w])", re.I)
MAG = {"k": 10**3, "thousand": 10**3, "m": 10**6, "million": 10**6,
       "b": 10**9, "bn": 10**9, "billion": 10**9, "trillion": 10**12}
UNIT_CANON = {"percent": "%", "per cent": "%", "hr": "hour", "hrs": "hour", "min": "minute",
              "mins": "minute", "sec": "second", "secs": "second", "yr": "year", "yrs": "year",
              "mi": "mile", "lbs": "lb"}

NAME_TOK = r"[A-Z][A-Za-z0-9'&-]*"
NAME_RX = re.compile(rf"\b{NAME_TOK}(?:[ \t]+(?:(?:of|de|del|la|von|van)[ \t]+)?{NAME_TOK})*")
STOP = set("""The A An In On At By For And But So Or If When While This That These Those It He She They We You I
My Our Your His Her Their Its As After Before Since Because However Also Then There Here What Why How Who Where
Which With Without From To Of Not No Yes Please Thanks Thank Dear Hello Hi Regards Sincerely Best Additionally
Moreover Therefore Overall Note Today Yesterday Tomorrow Now Once Each Every Some Many Most All Both One Two
Three Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July
August September October November December Jan Feb Mar Apr Jun Jul Aug Sep Sept Oct Nov Dec Is Are Was Were
Do Does Did Can Could Will Would Should May Might Must Let Yet Still Just Only Even Over Under Between Per
Via Re Mr Mrs Ms Dr""".split())


def _mask(text: str, span: tuple[int, int]) -> str:
    return text[:span[0]] + " " * (span[1] - span[0]) + text[span[1]:]


def _add(found: dict, kind: str, key: str, raw: str) -> None:
    found[kind].setdefault(key, raw.strip())


def _norm_unit(u: str) -> str:
    u = re.sub(r"\s+", " ", u.lower())
    u = UNIT_CANON.get(u, u)
    if len(u) > 3 and u.endswith("s") and u not in UNIT_CANON.values():
        u = u[:-1]
    return u


def _num_key(m: re.Match) -> str:
    val = Decimal(m.group("val").replace(",", "") + ("." + m.group("dec") if m.group("dec") else ""))
    cur = m.group("cur") or ""
    unit = (m.group("att") or m.group("unit") or "").strip()
    ul = unit.lower()
    if ul in MAG:
        val *= MAG[ul]
        unit = ""
    elif ul in ("dollar", "dollars", "usd"):
        cur, unit = "$", ""
    elif unit:
        unit = _norm_unit(unit)
    s = format(val.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return f"{cur}{s}{unit}"


def _date_key(m: re.Match) -> str:
    g = m.groupdict()
    mon = g.get("mon")
    month = MONTHS[mon[:3].lower()] if mon else int(g["m"])
    y = g.get("y")
    if y and len(y) == 2:
        y = "20" + y
    d = int(g["d"]) if g.get("d") else None
    return f"{y or '????'}-{month:02d}-{d:02d}" if d else f"{y or '????'}-{month:02d}"


def _cite_key(raw: str) -> str:
    s = raw.lower().replace("§", "sec")
    s = re.sub(r"\b(?:article|art)s?\b\.?", "art", s)
    s = re.sub(r"\b(?:section|sec)s?\b\.?", "sec", s)
    s = re.sub(r"[\s.]", "", s)
    return s.rstrip("-")


def extract(text: str) -> dict[str, dict[str, str]]:
    """Return {kind: {normalised key: raw text}} for every checkable item."""
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    found: dict[str, dict[str, str]] = {k: {} for k in KINDS}

    def sweep(rx, kind, keyfn):
        nonlocal text
        for m in list(rx.finditer(text)):
            _add(found, kind, keyfn(m), m.group(0))
            text = _mask(text, m.span())

    sweep(URL_RX, "url", lambda m: m.group(0).rstrip(".,;:!?").lower().rstrip("/"))
    sweep(EMAIL_RX, "email", lambda m: m.group(0).lower())
    sweep(QUOTE_RX, "quote", lambda m: re.sub(r"\s+", " ", m.group(1)).strip().rstrip(",.;"))
    for rx in CITE_RXS:
        sweep(rx, "cite", lambda m: _cite_key(m.group(0)))
    sweep(FORM_RX, "form", lambda m: (m.group("pre") + m.group("id")).upper().rstrip("-"))
    for rx in DATE_RXS:
        sweep(rx, "date", _date_key)
    sweep(NUM_RX, "number", _num_key)

    for m in NAME_RX.finditer(text):
        toks = m.group(0).split()
        while toks and toks[0] in STOP:
            toks.pop(0)
        if not toks:
            continue
        before = text[text.rfind("\n", 0, m.start()) + 1:m.start()].rstrip()
        starts = (before == "" or re.fullmatch(r"(?:[-*•#>]+|\d+[.)])", before) is not None
                  or before[-1] in '.!?:"(')
        if len(toks) == 1:
            t = toks[0]
            if t in STOP or len(t) < 2:
                continue
            if not t.isupper() and starts and toks == m.group(0).split():
                continue
        _add(found, "name", " ".join(toks), " ".join(toks))
    return found


def compare(src: dict, new: dict) -> dict:
    out = {}
    for kind in KINDS:
        s, n = src[kind], new[kind]
        dropped = {k: v for k, v in s.items() if k not in n}
        added = {k: v for k, v in n.items() if k not in s}
        changed = []
        for dk in list(dropped):
            best, bscore = None, 0.0
            for ak in added:
                score = difflib.SequenceMatcher(None, dk, ak).ratio()
                if score > bscore:
                    best, bscore = ak, score
            single = len(dropped) == 1 and len(added) == 1 and kind in ("cite", "form", "date", "number")
            if best is not None and (bscore >= 0.5 or single):
                changed.append({"from": dropped.pop(dk), "to": added.pop(best)})
        if dropped or added or changed:
            out[kind] = {"added": sorted(added.values()), "dropped": sorted(dropped.values()),
                         "changed": changed}
    return out


def diff_texts(source: str, rewrite: str) -> dict:
    src, new = extract(source), extract(rewrite)
    kinds = compare(src, new)
    return {"clean": not kinds, "kinds": kinds,
            "source_items": {k: len(v) for k, v in src.items() if v},
            "rewrite_items": {k: len(v) for k, v in new.items() if v}}


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    args = [a for a in argv if a != "--json"]
    if len(args) != 2 or any(a.startswith("--") for a in args):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        res = diff_texts(_read(args[0]), _read(args[1]))
    except OSError as exc:
        print(f"unit_diff: {exc}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(res, indent=1))
    else:
        for kind, d in res["kinds"].items():
            for item in d["dropped"]:
                print(f"[DROPPED] {kind}: {item}")
            for item in d["added"]:
                print(f"[ADDED]   {kind}: {item}")
            for ch in d["changed"]:
                print(f"[CHANGED] {kind}: {ch['from']}  ->  {ch['to']}")
        print("unit_diff: clean" if res["clean"] else "unit_diff: MISMATCH (fix the rewrite or confirm with the user)")
    return 0 if res["clean"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
