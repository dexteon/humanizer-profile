#!/usr/bin/env python3
"""Optional Jev second opinion on a humanizer rewrite.

Asks Jev (TypeSafe System One) four yes/no questions through Teon's sanctioned
adapter (scrub, privacy routing and spend meter apply):

  meaning_preserved  the rewrite keeps every claim, number, name, date, request
                     and level of certainty from the original
  added_claims       the rewrite adds a fact, number, citation or first-person
                     experience the original does not contain
  reads_ai           a careful reader would judge the rewrite AI-written
  voice_match        (only with --voice) the rewrite sounds like the sample's author,
                     compared with how much the original did. EXPERIMENTAL: in the
                     2026-10-14 test Jev scored an AI draft and a good rewrite the
                     same (0.39 vs 0.40), so it does not discriminate voice yet.
                     Rely on the fingerprint for voice; use Jev for meaning.

Usage:
    python jev_check.py --original IN.txt --rewrite OUT.txt [--voice SAMPLE.txt]
                        [--privacy-class personal|business|public|sensitive] [--json]

Exit: 0 all clear, 1 a check failed its threshold, 2 Jev unavailable or refused
(the rewrite proceeds without Jev; say so). Advisory only: a verdict never
blocks or ships anything on its own.

Adapter path: $HUMANIZER_JEV_ADAPTER, else D:/DexProjects/claude-config/scripts.
Text containing personal-record markers (medical, VA, court, i-love-me) is
refused for live calls by the adapter; this script then retries once with
privacy class "sensitive", which runs on the local judge.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ADAPTER_DIR = os.environ.get("HUMANIZER_JEV_ADAPTER", "D:/DexProjects/claude-config/scripts")
VOICE_WORDS = 450  # excerpt size; keeps state well under the adapter's token cap
TEXT_WORDS = 1800

# probability thresholds: a check "fails" when it crosses these
# voice_match is judged relative to the original (Jev's absolute voice scores on short
# samples run low: an unedited AI draft scored 0.26, a good rewrite 0.37), so it fails
# only when the rewrite sounds LESS like the author than the original did.
FAIL_IF = {"meaning_preserved": ("<", 0.6), "added_claims": (">", 0.4), "reads_ai": (">", 0.6)}
VOICE_SLACK = 0.02

QUESTIONS = {
    "meaning_preserved": "Ignore greetings, pleasantries, filler and enthusiasm wording. Does REWRITE keep every "
                         "substantive fact, number, name, date, request and commitment from ORIGINAL, without "
                         "changing, dropping or strengthening any of them?",
    "added_claims": "Does REWRITE state any fact, number, statistic, citation or first-person experience "
                    "(such as 'I ran', 'we found', 'in my experience') that ORIGINAL does not contain?",
    "reads_ai": "Would a careful human reader judge REWRITE as written by an AI assistant rather than by a person?",
    "voice_match": "Does REWRITE sound like it was written by the same person who wrote VOICE_SAMPLE, judging "
                   "word choice, sentence length, punctuation habits and tone, not topic?",
}


def clip(text: str, n: int) -> str:
    words = text.split()
    return " ".join(words[:n]) + (" [...]" if len(words) > n else "")


def run(original: str, rewrite: str, voice: str | None, privacy: str) -> dict:
    sys.path.insert(0, ADAPTER_DIR)
    try:
        import jev_adapter  # type: ignore
    except ImportError as e:
        return {"outcome": "UNAVAILABLE", "reason": f"adapter import failed: {e}"}
    state = {"texts": {"ORIGINAL": clip(original, TEXT_WORDS), "REWRITE": clip(rewrite, TEXT_WORDS)}}
    qs = {k: {"type": "noul", "instructions": v} for k, v in QUESTIONS.items() if k != "voice_match"}
    if voice:
        state["texts"]["VOICE_SAMPLE"] = clip(voice, VOICE_WORDS)
        qs["voice_match"] = {"type": "noul", "instructions": QUESTIONS["voice_match"]}
        qs["voice_match_original"] = {"type": "noul", "instructions":
                                      QUESTIONS["voice_match"].replace("Does REWRITE", "Does ORIGINAL")}
    used = privacy
    try:
        d = jev_adapter.ask(state, qs, caller="humanizer.check", privacy_class=privacy)
    except Exception as e:  # JevError on marker or privacy refusal
        if privacy == "sensitive":
            return {"outcome": "REFUSED", "reason": str(e)[:300]}
        used = "sensitive"
        try:
            d = jev_adapter.ask(state, qs, caller="humanizer.check", privacy_class="sensitive")
        except Exception as e2:
            return {"outcome": "REFUSED", "reason": str(e2)[:300]}
    res = {"outcome": d.outcome, "privacy_class": used, "model": d.model,
           "latency_ms": d.latency_ms, "reason": d.reason, "checks": {}}
    if not d.ok:
        return res
    probs = {}
    for k, v in d.answers.items():
        p = v.get("noul", v.get("probability")) if isinstance(v, dict) else v
        try:
            probs[k] = float(p)
        except (TypeError, ValueError):
            res["checks"][k] = {"p": None, "status": "unreadable", "raw": str(v)[:120]}
    for k, (op, t) in FAIL_IF.items():
        if k in probs:
            p = probs[k]
            bad = p < t if op == "<" else p > t
            res["checks"][k] = {"p": round(p, 3), "status": "FAIL" if bad else "ok", "threshold": f"{op}{t}"}
    if "voice_match" in probs and "voice_match_original" in probs:
        p, base = probs["voice_match"], probs["voice_match_original"]
        res["checks"]["voice_match"] = {"p": round(p, 3), "status": "FAIL" if p < base - VOICE_SLACK else "ok",
                                        "threshold": f"vs original {round(base, 3)} (delta {round(p - base, 3):+})"}
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--original", required=True)
    ap.add_argument("--rewrite", required=True)
    ap.add_argument("--voice")
    ap.add_argument("--privacy-class", default="personal")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    read = lambda p: Path(p).read_text(encoding="utf-8", errors="replace")
    res = run(read(a.original), read(a.rewrite), read(a.voice) if a.voice else None, a.privacy_class)
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"jev: {res['outcome']} {res.get('privacy_class', '')} {res.get('model', '')} {res.get('reason', '')}".strip())
        for k, c in res.get("checks", {}).items():
            thr = c.get("threshold", "")
            note = thr if thr.startswith("vs") else f"fail if {thr}"
            print(f"  {c['status']:>4} {k}: p={c['p']} ({note})")
    if res["outcome"] != "OK":
        return 2
    return 1 if any(c["status"] == "FAIL" for c in res["checks"].values()) else 0


if __name__ == "__main__":
    sys.exit(main())
