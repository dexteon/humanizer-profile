# Voice Fingerprint Reference

`SKILL.md` reads this file from the "Saved Profile and Voice Fingerprint" section when voice matching is enabled. The goal is a compact stylometric fingerprint extracted once and reused, not a raw sample pasted into every rewrite.

Voice matching runs entirely through the host LLM and local files. No external service. No Mac dependency. The single rewrite pass in `SKILL.md` consumes the fingerprint as constraints; this file never adds extra rewrite loops.

## Storage

Voices are multi-target: one folder per named voice under `$HOME/.humanizer/voices/`. A voice applies to a rewrite only when named (`voice=<name>`); there is no forced global voice.

- Sample: `$HOME/.humanizer/voices/<name>/sample.txt` (or an inline `voice=<path>` ad-hoc override)
- Fingerprint cache: `$HOME/.humanizer/voices/<name>/fingerprint.json`

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
- Record punctuation habits truthfully, but note that the rewrite never
  reproduces em-dashes or en-dashes even if the author uses them: the §14 ban
  always converts them. If the sample uses them, say so in `punctuation_quirks`
  and add "never reproduce the dashes" so the trait is not mistaken for a target.
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

Hash on Windows (PowerShell) — hash the resolved sample, not a fixed path:
```powershell
$h = (Get-FileHash "$voice_dir/sample.txt" -Algorithm SHA256).Hash.ToLower()
"sha256:$h"
```

Then show the populated JSON and ask "Looks right? (Yes / Edit / Re-extract)". On Yes, write it:
```powershell
$json | Set-Content "$voice_dir/fingerprint.json" -Encoding utf8
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

Never import facts, names, or anecdotes from the sample. The rewrite's content comes only from the source text being humanized. The em-dash ban and the "do not alter verbatim quotes, legal text, section numbers, or data" rule override everything here.

## Failure modes

| Mode | What to tell the user | Behavior |
|---|---|---|
| LLM extraction error | "Voice extraction failed, running without voice matching for this call." | `voice_active=false`; normal rewrite. |
| Sample under 50 words | "That sample is under 50 words. Paste at least 50, or run without voice matching." | Do not create the voice folder or write any files. |
| Binary / unreadable sample | "Could not read that as plain text, running without voice matching." | `voice_active=false`; normal rewrite. |
| Edited JSON drops a field | "That edit removed required fields. Restore the schema or re-extract." | Do not save. |
