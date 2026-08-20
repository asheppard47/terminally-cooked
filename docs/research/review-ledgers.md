---
version: "1.0.0"
schema_version: 2
title: "External Review Ledgers"
doc_type: detail
parent: INDEX.md
last_updated: 2026-08-19
last_audit: 2026-08-19
audit_status: current
domain: docs
triggers:
  - "med arb findings"
  - "review ledger"
  - "external critique"
---
# External Review Ledgers

**Three external review passes shaped this product: two adversarial design reviews that killed the original business model and rebuilt the scoring system, and one game-industry icon review that rewrote the art pipeline.** Each is recorded with what was confirmed, what was rejected, and why — a rejected finding is as load-bearing as an accepted one.

## Wave 1 — concept review (2026-08-18)

Two external reviewers, one wave, on the full concept brief. One returned 24 findings including 8 critical; the other returned 40 findings including 8 critical. They converged independently, which is itself signal. Ten clusters after deduplication:

| Cluster | Ruling |
|---|---|
| Contributors cannot license employer work product | CONFIRMED — kills dataset sales |
| "Synthetic" derivation cures neither rights nor leakage | CONFIRMED — kills dataset sales |
| No buyer; labs hold better first-party traces with legal cover | CONFIRMED — kills dataset sales |
| A post-hoc tool cannot reconstruct the event ledger | **REJECTED** — Claude Code persists a full ordered local transcript; the reviewers lacked that context |
| Priority contradiction: corpus called the goal, V1 collects nothing | CONFIRMED — split into two products, kept the fun one |
| A comedy funnel selects the wrong population for research data | CONFIRMED — reinforced the marketing-only reshape |
| Deferred collection is a purpose change that poisons consent | CONFIRMED — zero-upload made permanent |
| Condition multipliers are theatre; an honor-system board is meaningless | CONFIRMED — hosted board killed, conditions demoted to descriptive |
| Session unit undefined; "diff economy" is not an observable | CONFIRMED — unit frozen, metric dropped |
| Fever-meter plus engine scope recreates the killed predecessor | CONFIRMED — CLI and local HTML only |

## Wave 2 — scoring review (2026-08-19)

One reviewer at high effort returned 11 findings on the v0.4 scoring redesign. The second leg failed twice on execution-budget kills and was reported unavailable rather than substituted.

| Finding | Ruling and action |
|---|---|
| Chain class does not reliably mean serialized decisions | PARTIAL — LET IT COOK made error-aware; Test Whisperer demoted to flavor; ONE-SHOT WONDER kept as a genuine zero-error sequence |
| Correlated chains double-count toward the cap | CONFIRMED — streak-derived chains collapsed into one exclusive group |
| Sparse windows hold the chain indefinitely | CONFIRMED, real bug — one quiet window holds, two reset |
| Out-of-order timestamps corrupt window bucketing | CONFIRMED — negative bucket indices discarded |
| Fingerprint overclaims verification | CONFIRMED — relabeled a recompute identifier, with the narrower claim documented |
| Transcript-controlled metadata can inject markup or escapes | CONFIRMED, best catch of the wave — sanitisation added with a test |
| Test tallies are naive and farmable | PARTIAL — impact defused by demotion to flavor; parsing later gated on test-shaped commands after a live failure |
| Doom loop is not strictly adjacent | PARTIAL — the joke tolerates intervening reads; card copy corrected to drop the "in a row" claim |
| Fixed wall-clock windows measure session shape | ACCEPTED AS COARSE — rolling windows rejected for complexity, limitation documented |
| Tool success is not task success | ACCEPTED AS COARSE — the card says "green results", never "wins" |
| Flavor survives a failed session | INTENTIONAL — comedy survives failure; card now splits skill and comedy so the total is not misread |

## Wave 3 — icon review (2026-08-19)

A vision model briefed as a game-industry icon designer reviewed the rendered set at true display sizes on the real card background.

| Severity | Finding | Action |
|---|---|---|
| Blocker | Baked-in nameplates consume ~15% of canvas and become sub-pixel noise at 32 px | Names moved to the UI layer; art regenerated textless |
| Major | High-frequency detail collapses into mush at small sizes | "Bold primary shapes, no micro-debris" added to the template |
| Major | Monochrome warm palettes lose their silhouette on a dark UI | Rim-light halo and value separation made mandatory |
| Major | Inconsistent framing and palette across the set | Locked palette, locked framing, and per-badge focus modes |
| Fix | Naive downscaling wastes the tile | Dedicated 32 px level of detail with center-zoom crop and boosted contrast |

## Practices worth keeping

- **Review the plan before spending.** The X research plan was reviewed before any metered call; the reviewers rewrote the queries, added anti-promotion filters, and forced observability tagging at collection time. That pass prevented an entire wasted research budget.
- **Report failed legs honestly.** Two reviewer legs died on execution budgets. Neither was silently replaced, and the arbitration proceeded on the surviving evidence with the gap stated.
- **Reject with reasons.** The strongest single finding of wave 1 was wrong because the reviewer lacked one fact about local transcripts. Recording that rejection is what stops it being re-litigated every session.
