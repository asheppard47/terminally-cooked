---
name: terminally-cooked
description: >
  Grade a juicy AI-coding session from today into a local comedy results card
  (Terminally Cooked). Never grade the session that invoked this skill — that
  card has no insight. Use when the user says "grade this session", "grade my
  session", "session card", "terminally cooked", "llm grader", "roast this
  session", or wants a shareable diff-counter scorecard from a Claude Code,
  Codex, Grok, or Gemini CLI transcript.
---

# Terminally Cooked

Run the CLI in this repo. Do not reimplement scoring.

**Never grade the session you are currently in.** The invoking chat is a
probe, not a work session. Omit the path and let the CLI skip the live
session, then pick the meatiest other session from today (tool-result volume
and duration). If today has nothing else, it looks back one week. Do not pass
the current transcript path, uuid, or rollout file.

```bash
python3 grade_session.py            # juicy session from today, never the live one
python3 grade_session.py <uuid>     # a specific other session (not the live one)
python3 grade_session.py path/to/session.jsonl
python3 grade_session.py --html     # also write a standalone HTML card
python3 grade_session.py --share    # copy a caption locally; user pastes to X
python3 test_grade_session.py
```

A Codex rollout file, a Grok session directory, or a Gemini chat file works
the same way when the user names a specific *other* session. The card stamps
the adapter. Cross-harness scores are different games.

Badge art lives in `assets/badges/` next to the script and is inlined as data
URIs. Keep that directory with the script. Never fetch badges from the network.

## Repair without breaking intent

Transcript formats change. When a card looks wrong, an adapter fails open, or a
user reports a harness the parser does not understand, **fix detection and
parsing only**. The scoring contract is not yours to improve in passing.

**Allowed**
- Adapter / event-normalization fixes in `harness_adapters.py` so a real session
  shape maps onto the existing event contract
- Fail-open on unknown records, unknown tool outcomes, and missing fields
- Tests that pin the new session shape (fixture + expected counts)
- Docs that describe the newly observed transcript field

**Forbidden without an explicit owner decision and a new scoring-version string**
- Changing weights, caps, exponents, or which modifiers multiply vs add
- Adding, renaming, or re-thresholding catalog entries to "make the joke better"
- Adding network calls, upload, telemetry, analytics, or remote badge URLs
- Putting prompt text, file paths, repo names, branches, or tool output on a card
- Removing or softening the entertainment label
- Imputing subagent / child-session work into the parent score
- Ranking, leaderboards, or any claim that scores are comparable across people
- Grading the invoking session "just this once"

If a format change makes a modifier unobservable, leave it unawarded. Do not
invent a proxy metric.

The allowlist, privacy contract, and scoring model are the intent. A green test
suite after an adapter fix is necessary and not sufficient: also confirm a real
file from that harness still grades, and that HTML contains no `http` badge
source.

## How to invoke

Run `python3 grade_session.py` with no session argument from this repo root.
Show the ANSI card. Do not explain the skip/pick note unless the user asks how
the session was chosen. If they want to post it, `--html` and/or `--share`.
You do not post for them.
