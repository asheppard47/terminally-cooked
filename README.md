# LLM Grader

Grade one of your own Claude Code sessions into a comedy results card, rendered
in the hypnotic red/green terminal-diff aesthetic. Local-only, zero-upload:
reads the session transcript already on your disk, computes raw observable
counts (green/red tool results, streaks, test-tally deltas), attaches comedy
buffs/debuffs, and prints an ANSI card. The score is entertainment and says so
on the card.

```bash
python3 grade_session.py            # grade your most recent session
python3 grade_session.py a3a4d4fb   # grade by session-uuid prefix
python3 grade_session.py path/to/session.jsonl
```

## Privacy contract (permanent)

- Nothing leaves the machine. No network calls exist in this codebase.
- Card fields are allowlisted: session-uuid prefix, date, duration, model and
  effort names, event counts, buff names, score. No cwd, repo names, branch
  names, file paths, prompt text, or tool output ever reaches the card.
- Sharing a card is something the player does themselves, never the tool.

## Status

V1 prototype (2026-08-18). Concept SSOT + design/review history:
`~/repos/personal/Game Dev/learning/llm-grader-concept.md`.
Godot 4.x pinning: not applicable — this is a terminal tool, no engine.

Known couplings: parses Claude Code's internal transcript JSONL format
(`~/.claude/projects/*/<uuid>.jsonl`), which can change between Claude Code
versions. Tally detection matches `N passed[, M failed]` output and fails open.
