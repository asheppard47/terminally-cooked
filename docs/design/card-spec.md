---
version: "1.0.0"
schema_version: 2
title: "Card Specification"
doc_type: detail
parent: INDEX.md
last_updated: 2026-08-19
last_audit: 2026-08-19
audit_status: current
domain: docs
triggers:
  - "llm grader card"
  - "card fields"
  - "html card"
  - "ansi card"
---
# Card Specification

**The card is the product's only artifact, and it may contain nothing beyond the allowlisted fields below.** Two renderers exist — an ANSI terminal card printed on every run, and a standalone HTML card written on `--html` — and both draw from the same field set so a shared card can never reveal more than a terminal one.

## Allowlisted fields

| Field | Source | Example |
|---|---|---|
| Session identifier | first 8 chars of the session UUID | `a3a4d4fb` |
| Date | first transcript timestamp, date only | `2026-08-19` |
| Duration | first-to-last timestamp | `5h 55m` |
| Models | model names, sanitized | `claude-sonnet-5` |
| Effort levels | effort values, sanitized | `high` |
| Event counts | green, red, longest streak | `+36 / −2 / streak 22` |
| Test tally pair | first and last test-shaped tallies | `86 passed → 129 passed` |
| Tool histogram | tool names and call counts, top 6 | `Bash:17 Read:4` |
| Token totals | summed usage | `483.3M in · 1.18M out` |
| Modifiers | name, class, value, reason line | `FLOW STATE ×1.5 — 64 green results without a miss` |
| Score | final, plus skill and comedy split | `+3,460 (skill 3,060 · comedy 400)` |
| Provenance | scoring version and recompute stamp | `scoring-v0.4 · recompute: transcript dc89… · code a4a8…` |

Forbidden without exception: prompt text, tool output, file paths, repository names, branch names, working directory, and any raw diff content. `test_html_card_allowlist` enforces this by planting each forbidden category in a fixture and asserting absence in the render.

## Untrusted fields

Model and effort names originate in the transcript and are therefore attacker-influenced. Both are stripped to `[A-Za-z0-9._+\- ]` and truncated before rendering, which neutralises HTML injection into the share card and terminal-escape injection into the ANSI card. `test_meta_injection_sanitized` covers it.

## Layout contract

Both renderers present the same reading order, so a screenshot of either is recognisably the same object:

1. **Header** — session id, date, duration, models, effort
2. **Fever bar** — green-to-red ratio as a single filled bar
3. **Counts line** — green, errors, longest streak
4. **Diff tally** — the test pair rendered as a red removed line above a green added line, the aesthetic the whole product started from
5. **Tool histogram and token totals**
6. **Modifier list** — glyph, name, value tag, reason
7. **Footer** — final score with the skill/comedy split, scoring version, recompute stamp

## Visual language

The card is a diff, not a dashboard. Colors follow GitHub-dark conventions (`#0d1117` ground, `#3fb950` green, `#f85149` red, `#d29922` gold). Modifier class is encoded visually and identically in both renderers: chains take gold, debuffs red, flavor inert grey. Glyphs are monochrome terminal-native codepoints, never emoji — a deliberate rejection of the gamification patterns this audience mocks.

## Badge art integration

Painted badge art is produced per modifier at three levels of detail (1024 px, 72 px, 32 px). The 72 px asset is the chip in the HTML card; the 32 px asset is a center-zoom crop with contrast and saturation boosts so the subject survives at tile size. The art itself is textless — names are drawn by the renderer, never painted into the image. Rationale and pipeline: [art/style-guide.md](../art/style-guide.md) and [art/production-pipeline.md](../art/production-pipeline.md).

## Output rules

The HTML card is a self-contained fragment with an explicit `<meta charset="utf-8">` — without it the glyphs render as mojibake, which shipped once and was caught by screenshot review. The card is written to a local file; nothing transmits it.
