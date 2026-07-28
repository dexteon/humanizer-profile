# Writing Craft Rules (distilled from Anbeeld/WRITING.md v1.4.1, MIT)

Load this file when rewriting long-form or reader-facing prose (articles, docs, essays, emails, applications — anything a reader will actually see). It supplements the 33 patterns in SKILL.md with meaning-preservation guards and structural diagnostics. Everything here is a tripwire, not a target: scrutinize repeated fallback, not isolated use, and never invent material to force a change.

## Editing distortions (meaning-preservation guards)

A rewrite that changes meaning is a defect even when it reads better. Before delivering, compare source and result for:

- Certainty changes without evidence (`may` → `will`, `is` → `might be`).
- Scope drift (`some` → `most`, `often` → `always`, `in this sample` → `in general`).
- Lost negation, conditions, exceptions, comparisons, or qualifiers.
- Sequence converted to cause, or absence of evidence converted to proof. Keep `X caused Y`, `X drove Y`, `X proved Y` only when the source supports that relationship; otherwise use weaker relationship language.
- Detached or reassigned attribution; reported views or experience converted to narrator claims. Preserve who owns each claim.
- Exact terms replaced by weaker approximations; defined terms, names, numbers, units, dates, identifiers, and chronology must survive intact.
- Dialect, second-language features, deliberate repetition, or plainness normalized into prestige prose.
- Every sentence regularized to one cadence, length, polish, or formality.

## Never fabricate humanity

Extends SKILL.md's no-fabrication rule from facts to texture. The rewrite must not add:

- Typos, grammar errors, slang, or profanity as staged messiness.
- First-person experience, feelings, memories, preferences, relationships, or anecdotes the source (or the user) never supplied.
- Random variation or deliberate roughness inserted to "seem human." Fabricated humanity is as much a tell as sterile polish.

When a voice fingerprint is active, match the sample's habits, never its content: no facts, experiences, emotions, or identity claims extracted from the sample, and no caricature (amplified fragments, tics, or slang beyond what the sample actually does).

## Plain words and cohesion

- Prefer verbs over nominalizations (`decided` not `made a decision`; `use` not `utilization`) and people as subjects.
- Lead with the concrete; generalize after. In task-oriented text, put answers and actions first.
- Combine neighboring short sentences when syntax better carries the relationship; keep useful pauses. One-thought-per-sentence strings read as generated.
- Make transitions carry meaning (contrast, consequence, exception), not just sequence.

## Structural defaults to break

- Forced introduction-body-conclusion framing where the genre doesn't need it.
- Catalog prose: one paragraph per feature, date, stakeholder, or stage, with no relationships traced between them. Cross-connect, or consolidate lists of three or more parallel items around a single consequence, contrast, or example.
- Complete-looking taxonomies built from partial evidence; equal space for unequal sides. Uneven evidence deserves uneven space.
- Paragraph-closing type definitions and recap endings that restate rather than advance.
- Summaries that introduce a new claim or caveat, flatten disagreement, promote a side point into the conclusion, or make an open question sound resolved.

## Long-form diagnostics (run when the piece still feels generic)

- Name the most repeated visible move (sentence shape, opener, contrast frame, list rhythm). If it appears three or more times or dominates two consecutive paragraphs, rewrite one occurrence.
- Inspect recurring metaphors, oppositions, and phrasing families; keep a recurrence only when it shifts the argument.
- Remove restatement except in deliberate summaries or safety instructions.
- Confirm every claim-bearing paragraph has a supported concrete anchor, or narrow the paragraph. In criticism, reviews, or analysis, confirm at least one concrete-example paragraph.
- In work longer than four paragraphs, look for one supported example, qualification, or genuine doubling-back that prevents a pre-solved route.

## Watchlist additions (beyond SKILL.md's 33 patterns)

Flag on repetition: `The catch?` / `The surprising part?`, `Whether you're X or Y`, empty X-is-that wrappers (`The reality is that`), `called` before familiar nouns (`a method called testing`), `X today is not the X it was at the start`, unsupported upbeat turns after `despite these challenges`, `poised to` / `set to transform` without a forecast, repeated topic-reset openings, fake-human hedge chains (`I think... maybe... sort of`).

## Output integrity

- Strip unauthorized placeholders: `[Name]`, `[insert source]`, `TK`, `TBD`, `XX`, `202X`.
- Strip leaked machinery tokens: `turn0search0`, `oaicite`, `oai_citation`, `contentReference`.
- Verify markup: heading hierarchy, list structure, tables, code fences, footnotes, links (prefer original sources over search intermediaries; never fabricate or "fix" authenticated URLs).
- Leave code blocks, commands, datasets, and quotations unedited.

## Compound hyphenation

- Hyphenate temporary compounds before nouns (`a well-known author`, `a long-term plan`); usually open them after linking verbs (`the author is well known`, `the plan is long term`).
- Never hyphenate `-ly` adverb compounds (`highly qualified`, not `highly-qualified`).
- Keep conventional and ambiguity-preventing hyphens (`state-of-the-art`, `cost-effective`); follow the requested English variety and house style when exceptions matter.
