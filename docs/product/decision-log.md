---
version: "1.0.0"
schema_version: 2
title: "Decision Log"
doc_type: detail
parent: INDEX.md
last_updated: 2026-08-19
last_audit: 2026-08-19
audit_status: current
domain: docs
triggers:
  - "llm grader decisions"
  - "why no leaderboard"
  - "killed lineages"
---
# Decision Log

**Every ruling that constrains this product, with its date, its owner, and the evidence behind it.** Rulings marked CLOSED are not open for casual reversal; reopening one requires new evidence and a new dated entry, not a preference. Evidence sits in [research/review-ledgers.md](../research/review-ledgers.md) and the workshop X-research capsule.

## Closed rulings

| # | Date | Ruling | Basis |
|---|---|---|---|
| D1 | 2026-08-18 | **Rhythm-game predecessor archived.** A slow-classical rhythm game on the same diff aesthetic reached approved-core-loop stage and was archived for scope: chart authoring plus a real-time engine is a full game build. | Owner scope call |
| D2 | 2026-08-18 | **No sale of session-derived training data.** CLOSED — three independently fatal problems: contributors cannot license employer work product; "synthetic" derivation neither cures rights nor prevents leakage; no buyer exists, since labs hold better first-party traces with legal cover. | Both wave-1 reviewers, unanimous |
| D3 | 2026-08-18 | **Zero upload is permanent, not a V1 stage.** Deferred collection would be a purpose change that poisons consent and reads as malware to corporate security. Any corpus product must be separately named with fresh consent. | Wave-1 reviewers |
| D4 | 2026-08-18 | **Data layer reshaped to marketing and recognition only**, operating on card-level allowlisted fields, with submission as a separate explicit human act. | Owner, after D2 |
| D5 | 2026-08-18 | **No hosted leaderboard.** Self-reported local telemetry cannot be ranked honestly; ranking also invites farming. Corroborated externally: an internal AI-coding leaderboard at a large company reportedly produced "tokenmaxxing" of useless tasks before being scrapped. | Wave-1 reviewers + X research |
| D6 | 2026-08-18 | **Condition multipliers carry no fairness claim.** Model, effort, and compaction bonuses were dropped as ranked adjustments; conditions are descriptive only. | Wave-1 reviewers |
| D7 | 2026-08-18 | **Session unit frozen to one Claude Code session UUID.** Cross-tool ingestion and cross-session comparison are out of scope until each tool's unit can be mapped with evidence. | Wave-1 reviewers |
| D8 | 2026-08-19 | **Multipliers are reserved for serialized success; everything else adds flat.** Sustained error-free work scores superlinearly. | Owner directive, implemented as scoring v0.4 |
| D9 | 2026-08-19 | **Badge names are rendered by the UI, not painted into the art.** Baked-in nameplates degrade to noise at 32 px and cannot be made consistent across models. | Game-industry icon review |
| D10 | 2026-08-19 | **Art direction: painterly, luminous, textless.** Terminal-green/cyber palettes, neon "electric" grading, and photographic HDR vocabulary are all rejected. | Owner art direction |
| D11 | 2026-08-19 | **Blind A/B, one vote per person, outside parties.** Both models render identical prompts; votes are collected as native Telegram polls in a real developer group rather than solo judgment. | Owner; both review waves flagged solo comedy judgment as a defect |

| D12 | 2026-08-20 | **Scoring standard: one complete native session is the canonical unit.** No rolling lookback (invites boundary slicing), no best-session ladder (rewards grinding). Comparability rides the identity tuple — scoring version, division (blitz/sprint/long haul), delegation class, duration, recompute stamp — never the bare number. | Publish-review wave (Sol #10-11; Flash's normalized-rating proposal partially adopted as divisions-as-labels, rejected as a second score) |
| D13 | 2026-08-20 | **Subagent work is never imputed.** Sessions with subagent calls print a delegation class ("internals not graded"). Weighting Agent calls by duration or tokens fabricates precision about invisible work. | Publish-review wave (Sol #3 over Flash #2) |
| D14 | 2026-08-20 | **Share-to-X is caption-to-clipboard plus a blank composer.** No prefilled intent URLs and no upload APIs — both transmit the score before the user posts. The `--share` flag copies a caption from allowlisted fields and opens the composer; the user pastes. | Publish-review wave (Sol #16 over Flash #8) |
| D15 | 2026-08-20 | **Anti-cheat posture for publication: "self-attested, reproducible locally, not authenticated."** The recompute stamp stays; HMAC slugs with a public salt were rejected as forgeable theater. Honest reproduction is made cheap (published source, tagged releases) rather than pretending provenance. | Publish-review wave (Sol #12-13; Flash #7 rejected) |
| D16 | 2026-08-20 | **Public claim stays "Claude Code main-session transcripts."** The product does not claim to cover all LLM-assisted coding; other tools are future ingestion adapters, each needing its own session-unit mapping. | Publish-review wave (both reviewers) |

## Open questions

| Question | Status | Blocking |
|---|---|---|
| Which model's art ships per badge | Vote live in the Gentlemen Unicorn group, 24 matchups posted 2026-08-19 | Icon integration into the card |
| Persistent badges and a local history file | Deliberately unbuilt; audience research says session-scoped roasts are welcome and lifetime counters are mocked | Needs a history schema allowlist + idempotency tests first |
| Public release and naming | Not started; working name only | Name screening via the workshop naming playbook |
| Marketing and recognition lane | Designed as card-level only; waits for users | Real users |

## Reversal conditions

D2, D3 and D5 are the load-bearing ones. D2 and D3 reverse only with a specialist legal review plus a named buyer and a consent regime — that is a different product. D5 could reverse only if session capture became verifiable at the source (signed capture provenance), which no current tool provides.
