# LLM Grader

Grade one of your own AI-coding sessions into a comedy results card, rendered in
the red/green diff-counter aesthetic. Local-only, zero-upload: it reads the session
record already on your disk, counts what happened, attaches named achievements,
and prints a card. The score is entertainment and says so.

Supported harnesses (auto-detected from the file's own shape): **Claude Code**,
**Codex CLI**, **Grok CLI**, **Gemini CLI**. Pass a Codex rollout file, a Grok
session directory, or a Gemini chat file exactly like a Claude transcript. Cards
stamp their adapter — cross-harness scores are different games and say so.

```bash
python3 grade_session.py            # grade your most recent session
python3 grade_session.py a3a4d4fb   # grade by session-uuid prefix
python3 grade_session.py path/to/session.jsonl
python3 grade_session.py --html     # also write a shareable HTML card
python3 grade_session.py --share    # copy a caption to the clipboard + open X composer
python3 test_grade_session.py       # 28 tests
```

## Documentation

**[INDEX.md](./INDEX.md) is the doc tree** — start there. Sections:

| Section | What it owns |
|---|---|
| [docs/product/](./docs/product/INDEX.md) | Concept, privacy contract, decision log |
| [docs/design/](./docs/design/INDEX.md) | Scoring model, modifier catalog, card spec |
| [docs/art/](./docs/art/INDEX.md) | Badge style guide, production pipeline, voting protocol |
| [docs/engineering/](./docs/engineering/INDEX.md) | Architecture, transcript observables, testing |
| [docs/research/](./docs/research/INDEX.md) | External review ledgers, audience research |

## Privacy contract

Nothing leaves the machine. No network code exists in this repo. Card fields are
allowlisted — no prompt text, file paths, repo names, or tool output — and a test
enforces it. Sharing a card is something you do, never something the tool does.
Full contract: [docs/product/privacy-contract.md](./docs/product/privacy-contract.md).

## Status

V1 prototype, scoring v0.4, 24 modifiers, 24 tests green. Badge art is rendered and
out for a blind vote; persistent badges and public release are not built.
Known coupling: Claude Code's internal transcript JSONL format, which can change
between versions — see
[docs/engineering/transcript-observables.md](./docs/engineering/transcript-observables.md).
