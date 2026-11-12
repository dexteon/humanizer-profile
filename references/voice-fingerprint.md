# Voice Fingerprint Reference

`SKILL.md` reads this file from the "Saved Profile and Voice Fingerprint" section when voice matching is enabled. The goal is a compact stylometric fingerprint extracted once and reused, not a raw sample pasted into every rewrite.

Voice matching runs entirely through the host LLM and local files. No external service. No Mac dependency. The single rewrite pass in `SKILL.md` consumes the fingerprint as constraints; this file never adds extra rewrite loops.

## Storage

Voices are multi-target: one folder per named voice under `$HOME/.humanizer/voices/`. A voice applies when named inline (`voice=<name>`) or set as `default_voice` in the profile. See `references/profile-and-voice.md` for resolution and the loud-failure rule.

- Sample: `$HOME/.humanizer/voices/<name>/sample.txt` (or an inline `voice=<path>` ad-hoc override)
- Fingerprint cache: `$HOME/.humanizer/voices/<name>/fingerprint.json`
- Optional: `exemplars.txt` (rhythm passages) and `allow.json` (scanner allowlist), both described below. Neither is part of the cache key.

Below, `<voice_dir>` means `$HOME/.humanizer/voices/<name>` for the resolved voice.

On Windows, `$HOME` is `C:\Users\<you>`. The skill reads the sample fresh on each run. Neither file is uploaded by the skill itself, but the sample text travels with the host LLM's normal request path (cloud if the harness is cloud-based). Tell the user this when they opt in. Never copy private facts, names, or anecdotes from the sample into the fingerprint; the extraction prompt enforces that.

## Sample-size policy

- Recommended: 200+ words.
- Soft warn: 50-199 words. Say 200+ works better, then let them continue.
- Hard reject: under 50 words. Too thin for stable rhythm and function-word habits.
- Extraction cap: use only the first 3000 words. Store the full sample, cap extraction.

## Extraction prompt

Run this against the host LLM with the accepted sample, truncated to the first 3000 words. Fill the metadata fields yourself after the LLM returns the `fingerprint` object.

```text
You are a forensic writing-style analyst creating a reusable voice
fingerprint for a single-pass rewrite.

<task>
Analyze the writing sample and extract stable style traits. Return JSON only,
matching the schema exactly. Populate every field under `fingerprint`. Leave
the top-level metadata fields (`version`, `voice_name`, `sample_path`,
`sample_hash`, `sample_word_count`, `extracted_at`, `extracted_by`) as null;
the orchestrator fills these in.
</task>

<constraints>
- Focus on style, not topic.
- Do not copy private facts, names, claims, or anecdotes from the sample.
- Prefer observable habits over generic labels.
- Keep every string short enough to reuse in a prompt.
- If a trait is not visible, write "not enough evidence" for that field.
- Every field under `fingerprint` is required. Do not omit fields.
- Record punctuation habits truthfully, including em-dash or en-dash use.
  The §14 ban is absolute: a dash habit never re-enables dashes in the
  rewrite. Record where the author uses them so the rewrite puts the
  replacement comma, period, colon or parentheses at the same pauses.
</constraints>

<fields_to_watch>
Sentence length and variance, paragraph rhythm, openings and closings,
function words, contractions, hedges, punctuation, idioms, register, and
phrases the rewrite should avoid.
</fields_to_watch>

<schema>
{
  "version": 1,
  "voice_name": "<name>",
  "sample_path": "<sample-path>",
  "sample_hash": "<sha256-prefixed-hash>",
  "sample_word_count": <word-count>,
  "extracted_at": "<utc-iso8601>",
  "extracted_by": "<harness>:<model-id>",
  "fingerprint": {
    "voice_summary": "...",
    "avg_sentence_length": "12-18 words",
    "sentence_length_variance": "high|medium|low + one-line note",
    "signature_openings": ["...", "..."],
    "signature_closings": ["...", "..."],
    "function_word_habits": "...",
    "punctuation_quirks": "...",
    "register": "casual|casual-professional|professional|academic",
    "contraction_use": "high|medium|low",
    "hedge_use": "high|medium|low",
    "idiom_inventory": ["...", "..."],
    "paragraph_rhythm": "...",
    "do_list": ["...", "..."],
    "dont_list": ["...", "..."]
  }
}
</schema>

<writing_sample>
<paste sample here>
</writing_sample>
```

After the LLM returns, set the metadata fields yourself:

1. `version` = 1.
2. `voice_name` = the resolved voice name (the `<name>` folder under `voices/`).
3. `sample_path` = the resolved sample path (`<voice_dir>/sample.txt`).
4. `sample_hash` = `sha256:` plus the lowercase SHA-256 of the sample file.
5. `sample_word_count` = whitespace-token count (capped at 3000 if longer).
6. `extracted_at` = current UTC time in ISO 8601.
7. `extracted_by` = `<harness>:<model-id-or-unknown>`.

Hash on Windows (PowerShell). Each call is a fresh shell, so set the path in the same command:
```powershell
$name = "casual"; $d = "$HOME/.humanizer/voices/$name"
"sha256:" + (Get-FileHash "$d/sample.txt" -Algorithm SHA256).Hash.ToLower()
```

Then show the populated JSON and ask "Looks right? (Yes / Edit / Re-extract)". On Yes, write it:
```powershell
# $json holds the approved JSON text; WriteAllText avoids the PowerShell 5.1 byte-order mark
[IO.File]::WriteAllText("$HOME/.humanizer/voices/$name/fingerprint.json", $json)
```
On Edit, let the user correct fields but keep the schema; refuse to save if a required field is dropped. On Re-extract, ask what to change and rerun.

## Required fields

Top-level: `version`, `voice_name`, `sample_path`, `sample_hash`, `sample_word_count`, `extracted_at`, `extracted_by`, `fingerprint`.

Under `fingerprint`: `voice_summary`, `avg_sentence_length`, `sentence_length_variance`, `signature_openings`, `signature_closings`, `function_word_habits`, `punctuation_quirks`, `register`, `contraction_use`, `hedge_use`, `idiom_inventory`, `paragraph_rhythm`, `do_list`, `dont_list`.

A value of `"not enough evidence"` counts as populated. A cache missing any field is invalid: treat as a miss and re-extract.

## Cache invalidation

Cache key = `sha256:` over the resolved voice's sample file (`<voice_dir>/sample.txt`). Each voice caches independently. Re-extract when any of these is true:

- `<voice_dir>/fingerprint.json` is missing.
- `version` is not 1.
- `sample_hash` does not match the current sample hash.
- A required field is missing (including `voice_name`).
- The user runs `reset voice <name>` (deletes the whole `<voice_dir>`).

## How the fingerprint feeds the single rewrite pass

The rewrite in `SKILL.md` is one pass, not a loop. Apply the fingerprint as constraints on that pass:

- Register and function words: `register`, `contraction_use`, `hedge_use`, `function_word_habits`. These win over the profile's `tone=` on register conflicts (keep task-appropriate, allow the sample's natural contractions and transitions).
- Rhythm and texture: `avg_sentence_length`, `sentence_length_variance`, `paragraph_rhythm`.
- Surface habits: `signature_openings`, `signature_closings`, `idiom_inventory`, `punctuation_quirks`.
- `do_list` / `dont_list`: honor directly.

Never import facts, names, or anecdotes from the sample. The rewrite's content comes only from the source text being humanized. Never fabricate humanity either: no staged typos, grammar errors, slang, or invented first-person experience, and no caricature of the voice by amplifying its tics (see `references/writing-craft.md`). The "do not alter verbatim quotes, legal text, section numbers, or data" rule overrides everything here. The em-dash ban (§14) also holds unless the sample genuinely uses dashes, in which case match the sample's frequency.

## Exemplars (rhythm only)

A fingerprint describes a voice in words; two or three real passages show it. Exemplars are 2 to 3 verbatim passages from the voice sample, 40 to 120 words each, stored in `<voice_dir>/exemplars.txt` separated by a line containing only `---`. If the file is missing, pick them from `sample.txt` at rewrite time.

Rules for choosing and using them:

- **Off-topic.** Pick passages whose subject differs from the text being rewritten. A topic-matched exemplar pulls its content and phrasing into the rewrite and hurts the result.
- **Clean.** Skip passages with names, figures, dates or private facts, and passages that contain dashes (§14 still applies; a passage with a dash is not usable verbatim).
- **Varied.** Prefer one short-sentence passage, one long-sentence passage and, if the sample has it, one opening or closing.
- **Rhythm only.** Give them to the rewrite with this instruction: "These passages show how this author paces sentences, opens and closes, and punctuates. Match the rhythm. Do not reuse their words, subjects, claims or imagery." Content comes only from the text being rewritten.
- **Never a source of facts.** Nothing in an exemplar may appear in the output.

## Per-voice allowlist (`allow.json`)

Some habits that the scanner flags are simply how this author writes. `<voice_dir>/allow.json` lists the advisory tell ids the scanner should not flag for this voice:

```json
{
  "version": 1,
  "allow": ["31", "37", "38"],
  "notes": {"31": "short fragments are habitual", "37": "opens sentences with And or But", "38": "uses parentheses"}
}
```

- Typical ids: `31` (runs of short fragments), `37` (And, But or So openers), `38` (parenthetical asides), `10` (lists of three), `23` (a favourite filler).
- Add an id only when the sample shows the habit several times. Do not allowlist a tell because it is hard to remove.
- Hard tells (§14 dashes, §18 emoji, §19 curly quotes, §20 chatbot artifacts, §21 cutoff disclaimers) can never be allowlisted; the scanner ignores them in the file and says so.
- Pass it to the scanner with `tell_scan.py FILE --voice-dir <voice_dir>`. A missing `allow.json` means nothing is allowed. It is optional and is not part of the fingerprint schema, so it never invalidates the cache.
- Propose the allowlist when the fingerprint is first extracted (from `punctuation_quirks`, `signature_openings` and `paragraph_rhythm`) and let the user edit it.

## Failure modes

| Mode | What to tell the user | Behavior |
|---|---|---|
| LLM extraction error | "Voice extraction failed, running without voice matching for this call." | `voice_active=false`; normal rewrite. |
| Sample under 50 words | "That sample is under 50 words. Paste at least 50, or run without voice matching." | Do not create the voice folder or write any files. |
| Binary / unreadable sample | "Could not read that as plain text, running without voice matching." | `voice_active=false`; normal rewrite. |
| Edited JSON drops a field | "That edit removed required fields. Restore the schema or re-extract." | Do not save. |
