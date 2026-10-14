# Profile and Voice Reference

`SKILL.md` summarizes this under "Saved Profile and Voice Fingerprint". Read this file when a subcommand runs, when no profile exists yet, or when a voice must be resolved or extracted. Everything here is local files plus one analysis pass through the host LLM. Windows commands use PowerShell; substitute `$HOME` on other platforms. Each PowerShell call is a fresh shell, so every command below sets its own variables; never rely on a variable from an earlier call.

## Storage

Own namespace, separate from any other humanizer plugin:
- Profile (rewrite prefs only): `$HOME/.humanizer/profile.json`
- Voice library (one folder per named voice): `$HOME/.humanizer/voices/<name>/`
  - Sample: `$HOME/.humanizer/voices/<name>/sample.txt`
  - Fingerprint cache: `$HOME/.humanizer/voices/<name>/fingerprint.json`

Voices are multi-target: you can save more than one (e.g. `teon`, `teon-formal`, a client persona). A voice applies when it is named inline (`voice=<name>`) or set as `default_voice` in the profile. With neither, the rewrite is a generic de-AI pass in no particular persona.

Legacy note: earlier versions stored a single global `voice.txt` + `voice-fingerprint.json` and a `voice_path`/`voice_skip` in the profile. If you find those, migrate them once into `voices/<name>/` (ask the user for a name, default `me`), then remove the legacy files and the `voice_path`/`voice_fingerprint_hash`/`voice_skip` keys from the profile after the user confirms.

## Subcommands (handle these and stop, do not rewrite)

| User says | Action |
|---|---|
| `show profile` | Read and print `profile.json`, or say none saved. |
| `reset profile` | Delete `profile.json`, confirm. |
| `set dialect=us grade=10 tone=professional length=±10` | Write those keys into `profile.json` without an interview. Any subset allowed; missing keys keep current value or default. |
| `list voices` | List the folder names under `voices/`, and mark which is `default_voice` (or say "no default"). If none exist, say none saved. |
| `add voice <name>` | Prompt the user to paste a writing sample, save it to `voices/<name>/sample.txt`, then extract the fingerprint. Reject under 50 words; soft-warn 50-199; accept 200+. |
| `set voice <name>=<path>` | Copy the sample at `<path>` into `voices/<name>/sample.txt`. Extract on next rewrite. |
| `show voice <name>` | Print `voices/<name>/fingerprint.json` and its sample path. With no `<name>`, run `list voices`. |
| `reset voice <name>` | Delete the `voices/<name>/` folder after the user confirms. With no `<name>`, refuse and ask which voice (never delete all). |
| `default voice <name>` / `default voice off` | Set `default_voice` in `profile.json` to `<name>` (must exist) or clear it. |

## Profile resolution order

1. Inline overrides in the user's message (`dialect=`, `grade=`, `tone=`, `length=`) win for this call only; do not overwrite the file.
2. `skip-interview` flag: use saved profile if present, else defaults (dialect=us, grade=10/high-school, tone=professional, length=±10).
3. Saved `profile.json` exists and parses: use it silently, no interview.
4. No profile, no overrides: run the one-time interview below.

Read the profile:
```powershell
$p = "$HOME/.humanizer/profile.json"; if (Test-Path $p) { Get-Content $p -Raw } else { "NO_PROFILE" }
```
If missing, malformed, or missing required keys, treat as absent and run the interview.

**Interview** (only when needed). Use AskUserQuestion, one batched set:
- dialect: us | uk | other
- target_grade: 4 | 7 | 10 | 13 | 17
- tone: casual | professional | academic
- length_policy: ±10 (keep length) | exp (expand) | trim (shorten)

Then ask once: "Save these as your default so I stop asking?" If yes, write it. Use `WriteAllText`, not `Set-Content -Encoding utf8`, which writes a byte-order mark under Windows PowerShell 5.1 and breaks strict JSON readers:
```powershell
New-Item -ItemType Directory -Force "$HOME/.humanizer" | Out-Null
$prof = @{
  dialect = "us"; target_grade = 10; tone = "professional"; length_policy = "±10"
  default_voice = $null; saved_at = (Get-Date).ToUniversalTime().ToString("o"); version = 1
}
[IO.File]::WriteAllText("$HOME/.humanizer/profile.json", ($prof | ConvertTo-Json))
```
Inline overrides on a later call always beat the file for that one call and never rewrite it.

## Voice resolution order

Set `voice_active=false` by default, then:

1. Inline `voice=off` or `voice-skip`: skip voice for this call.
2. Inline `voice=<value>`: if the value contains `/` or `\` or ends in `.txt`, it is a path (step 3); otherwise it is a name. For a name, use `voices/<name>/`. If the folder does not exist, say so, list the available voices, and ask before continuing.
3. Inline `voice=<path>`: use that ad-hoc sample file this call only (not persisted). If unreadable, say so and ask before continuing.
4. `profile.json` has `default_voice` set: use `voices/<default_voice>/`.
5. Otherwise: no voice. Do a generic de-AI rewrite. Do NOT auto-prompt for a sample (capturing a voice is the opt-in `add voice <name>` subcommand).

**Loud failure rule.** If a voice was named or set as `default_voice` but cannot be loaded (folder missing, sample unreadable, fingerprint invalid, extraction failed), the first line of output must say `Voice '<name>' not loaded: <reason>`. When the text is written as the user (letters, emails, applications, resumes), stop and ask before rewriting without the voice. Never fall back silently.

Check one voice (set `$name` in the same command):
```powershell
$name = "teon"; $d = "$HOME/.humanizer/voices/$name"
"sample=" + (Test-Path "$d/sample.txt") + " fingerprint=" + (Test-Path "$d/fingerprint.json")
if (Test-Path "$d/sample.txt") { "sha256:" + (Get-FileHash "$d/sample.txt" -Algorithm SHA256).Hash.ToLower() }
```
If `fingerprint.json` exists, has `version` 1, its `sample_hash` matches the printed hash, and all required fields are populated: load it silently and set `voice_active=true`. Otherwise extract: run the extraction prompt from `references/voice-fingerprint.md` against the sample (first 3000 words), fill the metadata fields (including `voice_name`), show the JSON, ask "Looks right? (Yes / Edit / Re-extract)", then save it with `[IO.File]::WriteAllText`. Set `voice_active=true`.

## How the resolved settings feed the rewrite

This stays a single disciplined pass. Apply the resolved profile and fingerprint as constraints on that one rewrite, not as extra loops:
- `dialect`: spelling and idiom (us vs uk).
- `target_grade`: sentence complexity and vocabulary level (aim within about one grade).
- `tone`: register, but when `voice_active=true` the fingerprint's `register`, `contraction_use`, `hedge_use`, and `function_word_habits` win on register conflicts (keep it task-appropriate).
- `length_policy`: keep (±10%), expand, or trim.
- Voice fingerprint: match `signature_openings`, `paragraph_rhythm`, `idiom_inventory`, sentence-length pattern. Never import facts, names, or anecdotes from the sample; the rewrite's content comes only from the source text. Match the sample's habits, not staged imperfection: never fabricate typos, grammar errors, slang, or first-person experience the sample and source don't contain, and don't caricature the voice by amplifying its tics.

"Never alter verbatim quotes, legal text, section numbers, or data" overrides everything above. The em and en dash ban (§14) is absolute: no voice, sample or fingerprint re-enables them. Dash habits recorded in `punctuation_quirks` only tell the rewrite where the author pauses, so it can place the replacement comma, period, colon or parentheses there.
