---
version: "1.0.0"
schema_version: 2
title: "Art Voting Protocol"
doc_type: detail
parent: INDEX.md
last_updated: 2026-08-19
last_audit: 2026-08-19
audit_status: current
domain: docs
triggers:
  - "badge vote"
  - "art face-off"
  - "telegram poll"
---
# Art Voting Protocol

**Which render ships is decided by outside developers voting blind, one vote each, not by the author's taste.** Both external review waves identified solo comedy judgment as a structural defect: the person who invented the jokes, wrote the prompts and named the badges cannot also be the only judge of whether they land.

## Method

1. **Identical prompts, two models.** Any difference between the pair is the model, not the brief.
2. **Blind labels.** Renders are presented as "A (left)" and "B (right)"; voters are not told which model produced which, and the labels are consistent across all matchups (A = one model throughout, B = the other) so the tally is meaningful.
3. **One vote per person.** Native Telegram polls enforce this; the browser gallery is single-user only and is a review aid, not the ballot.
4. **Comments are first-class.** Voters are explicitly invited to reply with what they would change; a matchup that draws a specific complaint becomes a regeneration candidate regardless of its vote count.
5. **Judge at display size.** The review gallery shows every render at 1024 px, 72 px and 32 px on the real card background, because the badge ships as a tile, not a poster.

## Current round

Posted 2026-08-19 to a developer Telegram group: an intro setting context, then 24 matchups, each a side-by-side composite with the achievement's joke as caption followed by its own poll with public voters. Delivery confirmed complete — 24 photos, 24 polls, no failures.

## Tallying

When the round closes, read poll results and replies from the same authenticated session, then produce:

- a per-badge winner with vote counts,
- a per-model win/loss record across the set,
- a list of matchups whose comments flag a specific problem, marked for regeneration rather than promotion.

Winners are promoted into the repo as derivatives and wired into the card chips; losers stay in scratch under the workshop's draft retention window.

## Rules that keep the vote honest

- Never reveal model identity before the vote closes.
- Never re-render one side of a live matchup; a fix invalidates the pair and both sides must be regenerated.
- A tie or a badge whose comments are uniformly negative goes back to the prompt stage — the vote picks between two options, it does not certify that either is good.
