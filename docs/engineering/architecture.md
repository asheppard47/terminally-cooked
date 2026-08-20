---
version: "1.0.0"
schema_version: 2
title: "Architecture"
doc_type: detail
parent: INDEX.md
last_updated: 2026-08-19
last_audit: 2026-08-19
audit_status: current
domain: docs
triggers:
  - "llm grader architecture"
  - "grade_session structure"
  - "data flow"
---
# Architecture

**A single-file pipeline with four separable stages — locate, analyze, judge, render — where each stage hands the next a plain data structure and only the render stage knows about presentation.** The separation is what lets the scoring doctrine change without touching parsing, and lets a second renderer exist without duplicating logic.

## Data flow

```
find_session(arg)        → path to one session .jsonl
   ↓
analyze(path)            → stats dict: counts, streaks, windows, metadata, sha
   ↓
pick_buffs(stats)        → [(name, class, value, reason), …]
   ↓
score_parts(stats, buffs)→ (core, flat)
   ↓
render / render_html     → ANSI card, HTML card
```

## Responsibilities

| Function | Owns | Never does |
|---|---|---|
| `find_session` | resolving a path, a UUID prefix, or "most recent" | reading content |
| `iter_records` | streaming JSONL, skipping malformed lines | interpreting semantics |
| `analyze` | one pass producing every observable — counts, streaks, doom-loop runs, cook chain, time windows, tokens, models, effort, compaction, transcript hash | any scoring judgment |
| `pick_buffs` | the catalog: thresholds, classes, reason strings | arithmetic on the total |
| `score_parts` | the formula, caps, exponents, floor | deciding which modifiers fired |
| `render`, `render_html` | presentation, glyphs, layout | recomputing anything |
| `safe_meta` | sanitising transcript-sourced metadata for output | filtering content elsewhere |
| `fingerprint` | recompute identity stamp | claiming authenticity |

The single `analyze` pass is deliberate: streaks, spirals, doom-loop runs and window occupancy are all sequence-dependent, and computing them in separate passes invites disagreement between them.

## Key mechanics

**Streak and spiral** track consecutive non-error and error tool results respectively, each resetting the other.

**Doom loop** pairs a `tool_use` id to its command text in a pending map, then on the matching `tool_result` compares the command to the last failed command; identical and failed increments the run, any success clears it. Command text is used for comparison only and never rendered.

**Cook chain** counts consecutive green tool results with no intervening human text; a human message or an error resets it, so it measures unsupervised *success*, not unsupervised volume.

**Clean-window chain** buckets tool results into fixed 20-minute windows keyed off the first timestamp, marks a window clean when it holds at least 5 events and no errors, and walks the buckets: clean extends the run, an error resets it, one sparse window holds it, two consecutive sparse windows reset it. Negative bucket indices from out-of-order timestamps are discarded rather than silently folded into bucket zero.

## Interfaces

```bash
python3 grade_session.py                  # most recent session
python3 grade_session.py a3a4d4fb         # by UUID prefix
python3 grade_session.py path/to/x.jsonl  # explicit path
python3 grade_session.py --html [out.html]
```

Exit is non-zero with a clear message when no transcript matches. `FORCE_COLOR=1` forces ANSI color when stdout is not a TTY.

## Dependencies

Grading uses the standard library only. Pillow is required for the badge art pipeline and for the injection test's fixtures, not for grading. The transcript format is Claude Code's internal JSONL, which is the tool's principal coupling: see [transcript-observables.md](./transcript-observables.md) for how that risk is contained.
