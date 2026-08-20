#!/usr/bin/env python3
"""LLM Grader — grade one Claude Code session into a comedy results card.

Local-only, zero-upload. Reads a session transcript JSONL from
~/.claude/projects/<project-dir>/<session-uuid>.jsonl, computes raw observable
counts, attaches comedy buffs/debuffs, and renders an ANSI terminal card in the
red/green diff-counter aesthetic.

Card fields are ALLOWLISTED: no cwd, repo names, branch names, file paths,
prompt text, or tool output ever reaches the card. Concept SSOT:
~/repos/personal/Game Dev/learning/llm-grader-concept.md
"""

import argparse
import base64
import hashlib
import html as html_mod
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from harness_adapters import detect_harness, iter_events, session_identity

SCORING_VERSION = "scoring-v0.5 (entertainment only)"
CHAIN_PRODUCT_CAP = 6.0     # stacked chain multipliers cap ("within reason")
STREAK_EXP = 1.5            # serialized-event chain superlinearity
STREAK_CAP = 100
WINDOW_SECS = 1200          # 20-min windows for the sustained-skill meta-chain
WINDOW_MIN_EVENTS = 5
WINDOW_CHAIN_EXP = 1.5
WINDOW_CHAIN_UNIT = 150
WINDOW_CHAIN_CAP = 12
PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Known-format tally parsing (non-semantic; fails open on no-match).
TALLY_RE = re.compile(r"(\d+)\s+passed(?:,?\s+(\d+)\s+fail(?:ed|ures?))?", re.IGNORECASE)
OVERLOAD_RE = re.compile(r"overloaded|\b529\b", re.IGNORECASE)
# Tallies only count when the producing Bash command looks like a test run —
# otherwise quoted/echoed test numbers (docs, cards, logs) poison the delta.
TEST_CMD_RE = re.compile(
    r"pytest|py\.test|unittest|npm (?:run )?(?:test|e2e)|yarn test|pnpm test"
    r"|go test|cargo test|make test|mvn test|gradle test|playwright|cypress"
    r"|jest|vitest|phpunit|rspec|ctest|test_|_test|run_suite", re.IGNORECASE)
INTERRUPT_MARKER = "[Request interrupted"


def iter_records(path):
    with open(path) as f:
        for line in f:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def tool_result_text(block):
    inner = block.get("content")
    if isinstance(inner, str):
        return inner
    if isinstance(inner, list):
        return " ".join(x.get("text", "") for x in inner if isinstance(x, dict))
    return ""


def analyze(path, harness=None):
    """Grade one session from any supported harness. Detection is automatic;
    parsing is delegated to harness_adapters, bookkeeping happens here."""
    harness = harness or detect_harness(path) or "claude-code"
    session_id, hash_path = session_identity(path, harness)
    s = {
        "session_id": session_id,
        "harness": harness,
        "transcript_sha": hashlib.sha256(Path(hash_path).read_bytes()).hexdigest(),
        "models": {},
        "efforts": {},
        "tools": {},
        "green": 0,
        "red": 0,
        "unknown_results": 0,   # tri-state: results with no derivable success flag
        "longest_streak": 0,
        "worst_spiral": 0,
        "interruptions": 0,
        "compactions": 0,
        "first_tally": None,
        "last_tally": None,
        "first_ts": None,
        "last_ts": None,
        "user_prompts": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "yolo_mode": False,
        "plan_entries": 0,
        "overloads": 0,
        "longest_cook": 0,
        "night_events": 0,
        "worst_doom_loop": 0,
        "clean_window_chain": 0,
        "charm": False,        # a run of exactly 3 errors was followed by a success
    }
    streak = spiral = cook = 0
    windows = {}       # window index -> [events, errors]
    tallies = {}       # normalized test command -> [first_tally, last_tally, samples]
    pending = {}       # tool call id -> command string (never rendered)
    last_failed_cmd, doom_run = None, 0
    for ev in iter_events(path, harness):
        ts = ev.get("ts")
        if ts:
            s["first_ts"] = s["first_ts"] or ts
            s["last_ts"] = ts
            try:
                hour = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().hour
                if 2 <= hour < 6:
                    s["night_events"] += 1
            except ValueError:
                pass
        kind = ev["kind"]
        if kind == "compaction":
            s["compactions"] += 1
        elif kind == "permission":
            if ev["mode"] == "bypass":
                s["yolo_mode"] = True
            elif ev["mode"] == "plan":
                s["plan_entries"] += 1
        elif kind == "model":
            if ev.get("model"):
                s["models"][ev["model"]] = s["models"].get(ev["model"], 0) + 1
            if ev.get("effort"):
                s["efforts"][ev["effort"]] = s["efforts"].get(ev["effort"], 0) + 1
        elif kind == "usage":
            s["tokens_in"] += ev.get("input", 0)
            s["tokens_out"] += ev.get("output", 0)
        elif kind == "human":
            s["user_prompts"] += 1
            cook = 0
        elif kind == "interrupt":
            s["interruptions"] += 1
        elif kind == "tool_call":
            name = ev.get("name", "?")
            s["tools"][name] = s["tools"].get(name, 0) + 1
            if isinstance(ev.get("command"), str):
                pending[ev.get("id")] = ev["command"].strip()
        elif kind == "tool_result":
            success = ev.get("success")
            if ts and s["first_ts"]:
                try:
                    t0 = datetime.fromisoformat(s["first_ts"].replace("Z", "+00:00"))
                    tn = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    wi = int((tn - t0).total_seconds() // WINDOW_SECS)
                    if wi >= 0:  # out-of-order timestamps never land in a bucket
                        w = windows.setdefault(wi, [0, 0])
                        w[0] += 1
                        if success is False:
                            w[1] += 1
                except ValueError:
                    pass
            cmd = pending.pop(ev.get("id"), None)
            text = ev.get("text", "")
            if success is None:
                # tri-state: unknown outcomes touch neither streaks nor spirals
                s["unknown_results"] += 1
            elif success is False:
                s["red"] += 1
                cook = 0  # an error breaks the unsupervised-success chain
                if OVERLOAD_RE.search(text):
                    s["overloads"] += 1
                if cmd is not None:
                    doom_run = doom_run + 1 if cmd == last_failed_cmd else 1
                    last_failed_cmd = cmd
                    s["worst_doom_loop"] = max(s["worst_doom_loop"], doom_run)
                spiral += 1
                s["worst_spiral"] = max(s["worst_spiral"], spiral)
                streak = 0
            else:
                s["green"] += 1
                cook += 1  # unsupervised-success chain grows on green results only
                s["longest_cook"] = max(s["longest_cook"], cook)
                if cmd is not None:
                    last_failed_cmd, doom_run = None, 0
                streak += 1
                s["longest_streak"] = max(s["longest_streak"], streak)
                if spiral == 3:
                    s["charm"] = True   # exactly three errors, then this success
                spiral = 0
            if success is not None and cmd is not None and TEST_CMD_RE.search(cmd):
                m = TALLY_RE.search(text)
                if m:
                    tally = (int(m.group(1)), int(m.group(2) or 0))
                    # per-command tracking: deltas only compare like with like,
                    # so a full-suite run followed by one focused test can't
                    # register as a fictional regression
                    entry = tallies.setdefault(" ".join(cmd.split()), [tally, tally, 0])
                    entry[1] = tally
                    entry[2] += 1
    # pick the tally pair from the most-sampled test command (>=2 samples),
    # so first/last always describe the same suite
    picked = max(tallies.values(), key=lambda e: e[2], default=None)
    if picked and picked[2] >= 2:
        s["first_tally"], s["last_tally"] = picked[0], picked[1]
    elif picked:
        s["first_tally"] = s["last_tally"] = picked[1]   # single run: shown, no delta
    # only COMPLETED windows qualify: the in-progress final bucket is excluded,
    # so "three 20-minute windows" cannot be earned in twenty-one minutes
    last_bucket = max(windows) if windows else -1
    run = best = sparse = 0
    for i in range(last_bucket):
        ev, er = windows.get(i, (0, 0))
        if ev >= WINDOW_MIN_EVENTS and er == 0:
            run += 1
            sparse = 0
            best = max(best, run)
        elif er > 0:
            run = sparse = 0
        else:
            # sparse window: one holds the chain (thinking is allowed);
            # two consecutive reset it (walking away is not a chain)
            sparse += 1
            if sparse >= 2:
                run = sparse = 0
    s["clean_window_chain"] = best
    return s


# Badge glyphs: terminal-native monochrome codepoints, never emoji — the card
# is a diff, not a Duolingo streak. Paired arrows are deliberate: ↻ Doom Loop
# (repeating the same thing), ↺ Error Spiral (spinning backwards).
ICONS = {
    "ONE-SHOT WONDER": "◎", "FLOW STATE": "≋", "Clean Streak": "⇉",
    "LET IT COOK": "♨", "THE LONG GAME": "♟",
    "Red Wedding": "☠", "Error Spiral": "↺", "Doom Loop": "↻",
    "Backseat Driver": "‼", "All Plan No Game": "☰", "Twenty Questions": "¿",
    "Third Time's the Charm": "☘", "Overloaded": "⏻",
    "YOLO MODE": "»", "Token Bonfire": "🜂", "Night Shift": "☾",
    "Marathon": "∞", "Test Whisperer": "✓", "Speedrun": "↯",
    "Middle Manager": "⑂", "Lost the Tapes": "⌫", "Model Hopper": "⇄",
    "Bookworm": "¶", "Perfectly Balanced": "≍",
}

# Badge art: winning render per modifier, chosen by blind vote (see
# docs/art/voting-protocol.md). Embedded as data URIs so a shared card stays
# self-contained; the terminal card keeps the glyphs above.
BADGE_DIR = Path(__file__).parent / "assets" / "badges"
SLUGS = {
    "ONE-SHOT WONDER": "one_shot_wonder", "FLOW STATE": "flow_state",
    "Clean Streak": "clean_streak", "LET IT COOK": "let_it_cook",
    "THE LONG GAME": "long_game", "Red Wedding": "red_wedding",
    "Error Spiral": "error_spiral", "Doom Loop": "doom_loop",
    "Backseat Driver": "backseat_driver", "All Plan No Game": "all_plan_no_game",
    "Twenty Questions": "twenty_questions", "Third Time's the Charm": "third_times_charm",
    "Overloaded": "overloaded", "YOLO MODE": "yolo_mode",
    "Token Bonfire": "token_bonfire", "Night Shift": "night_shift",
    "Marathon": "marathon", "Test Whisperer": "test_whisperer",
    "Speedrun": "speedrun", "Middle Manager": "middle_manager",
    "Lost the Tapes": "lost_the_tapes", "Model Hopper": "model_hopper",
    "Bookworm": "bookworm", "Perfectly Balanced": "perfectly_balanced",
}


def badge_data_uri(name, size=72):
    """Return the badge art as a data URI, or None when the asset is absent."""
    slug = SLUGS.get(name)
    if not slug:
        return None
    path = BADGE_DIR / f"{slug}_{size}.png"
    if not path.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


SAFE_META_RE = re.compile(r"[^A-Za-z0-9._+\- ]")


def safe_meta(value, limit=40):
    """Model/effort names come from the transcript and are untrusted for
    rendering: strip to a conservative charset before ANSI or HTML output."""
    return SAFE_META_RE.sub("", str(value))[:limit]


def meta_names(d):
    return ", ".join(safe_meta(k) for k in sorted(d, key=d.get, reverse=True))


def duration_minutes(s):
    try:
        t0 = datetime.fromisoformat(s["first_ts"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(s["last_ts"].replace("Z", "+00:00"))
        return max(1, int((t1 - t0).total_seconds() // 60))
    except (AttributeError, ValueError, TypeError):
        return None


def division(s):
    """Session length class, like a chess time control. Labels only — divisions
    never normalize the score, they tell the reader which game was played."""
    mins = duration_minutes(s)
    if mins is None:
        return "?"
    if mins < 15:
        return "blitz"
    if mins < 120:
        return "sprint"
    return "long haul"


def delegation_note(s):
    n = s["tools"].get("Agent", 0)
    return f"delegation: {n} subagent call(s) · internals not graded" if n else None


def pick_buffs(s):
    """The modifier catalog. Three kinds:
    - "chain": multiplies — earned only by serialized sustained success
    - "debuff": multiplies down — errors are always real
    - "flavor": flat point bonus — context/comedy, never compounds
    Values are jokes, not measurement."""
    buffs = []  # (name, kind, value, line)
    total = s["green"] + s["red"]
    tools = s["tools"]
    mins = duration_minutes(s)

    # chains (serialized skill -> multiplies)
    # streak-derived chains are one correlated group: only the strongest applies
    if s["red"] == 0 and total >= 20:
        buffs.append(("ONE-SHOT WONDER", "chain", 1.6, "an entire session, zero errors. suspicious."))
    elif s["longest_streak"] >= 25:
        buffs.append(("FLOW STATE", "chain", 1.5, f"{s['longest_streak']} green results without a miss"))
    elif s["longest_streak"] >= 10:
        buffs.append(("Clean Streak", "chain", 1.2, f"{s['longest_streak']} in a row"))
    ft, lt = s["first_tally"], s["last_tally"]
    if s["longest_cook"] >= 50:
        buffs.append(("LET IT COOK", "chain", 1.3, f"{s['longest_cook']} straight green calls, zero supervision"))
    if s["clean_window_chain"] >= 3:
        buffs.append(("THE LONG GAME", "chain", 1.0 + 0.1 * min(s["clean_window_chain"], WINDOW_CHAIN_CAP),
                      f"{s['clean_window_chain']} consecutive clean 20-min windows"))

    # debuffs (multiply down)
    if s["worst_spiral"] >= 4:
        buffs.append(("Error Spiral", "debuff", 0.7, f"{s['worst_spiral']} consecutive faceplants"))
    elif s["worst_spiral"] == 3 and s["charm"]:
        buffs.append(("Third Time's the Charm", "debuff", 0.9, "3 straight errors, then grace"))
    if ft and lt and lt[1] > ft[1]:
        buffs.append(("Red Wedding", "debuff", 0.6, f"failures went {ft[1]} -> {lt[1]}"))
    if tools.get("AskUserQuestion", 0) >= 4:
        buffs.append(("Twenty Questions", "debuff", 0.9, f"asked the human {tools['AskUserQuestion']} times"))
    if s["interruptions"] >= 3:
        buffs.append(("Backseat Driver", "debuff", 0.8, f"human slammed the brakes {s['interruptions']} times"))
    if s["plan_entries"] >= 1 and tools.get("Edit", 0) + tools.get("Write", 0) == 0:
        buffs.append(("All Plan No Game", "debuff", 0.8, f"entered plan mode {s['plan_entries']}x, zero Edit/Write calls"))
    if s["overloads"] >= 1:
        buffs.append(("Overloaded", "debuff", 0.9, f"the API said no, {s['overloads']}x (rare)"))
    if s["worst_doom_loop"] >= 3:
        buffs.append(("Doom Loop", "debuff", 0.7, f"same command failed {s['worst_doom_loop']}x"))

    # flavor (flat bonus, never compounds)
    if ft and lt and lt[0] > ft[0]:
        buffs.append(("Test Whisperer", "flavor", 150, f"{ft[0]} passed -> {lt[0]} passed"))
    if s["yolo_mode"]:
        buffs.append(("YOLO MODE", "flavor", 250, "--dangerously-skip-permissions. respect."))
    if s["tokens_in"] >= 100_000_000 or s["tokens_out"] >= 1_000_000:
        buffs.append(("Token Bonfire", "flavor", 200, f"{s['tokens_in']/1e6:.0f}M tokens. the meter is spinning."))
    if s["night_events"] >= 10:
        buffs.append(("Night Shift", "flavor", 200, "real work happening between 2 and 6 am"))
    if mins and mins >= 240:
        buffs.append(("Marathon", "flavor", 200, f"{mins // 60}h {mins % 60}m in the chair"))
    elif mins and mins <= 10 and total >= 10:
        buffs.append(("Speedrun", "flavor", 150, f"in and out in {mins} minutes"))
    if tools.get("Agent", 0) >= 5:
        buffs.append(("Middle Manager", "flavor", 150, f"delegated to {tools['Agent']} subagents"))
    if s["compactions"] >= 1:
        buffs.append(("Lost the Tapes", "flavor", 100, f"survived {s['compactions']} compaction(s); records incomplete"))
    if len(s["models"]) >= 3:
        buffs.append(("Model Hopper", "flavor", 100, f"{len(s['models'])} different models in one session"))
    reads, bashes = tools.get("Read", 0), tools.get("Bash", 0)
    if reads >= 20 and reads > bashes:
        buffs.append(("Bookworm", "flavor", 50, f"read {reads} files, touched grass never"))
    if not buffs:
        buffs.append(("Perfectly Balanced", "flavor", 0, "as all things should be"))
    return buffs


def score_parts(s, buffs):
    """Chains multiply (capped); serialized success scores superlinearly;
    flavor adds flat on top of the floored core; debuffs bite the core."""
    base = s["green"] * 10 - s["red"] * 15
    base += int(min(s["longest_streak"], STREAK_CAP) ** STREAK_EXP)
    base += int(WINDOW_CHAIN_UNIT * min(s["clean_window_chain"], WINDOW_CHAIN_CAP) ** WINDOW_CHAIN_EXP)
    ft, lt = s["first_tally"], s["last_tally"]
    if ft and lt:
        base += (lt[0] - ft[0]) * 25
    chain = 1.0
    debuff = 1.0
    flat = 0
    for _, kind, value, _ in buffs:
        if kind == "chain":
            chain *= value
        elif kind == "debuff":
            debuff *= value
        else:
            flat += value
    chain = min(chain, CHAIN_PRODUCT_CAP)
    return max(0, int(base * chain * debuff)), flat


def score(s, buffs):
    core, flat = score_parts(s, buffs)
    return core + flat


class C:
    on = sys.stdout.isatty() or os.environ.get("FORCE_COLOR")
    @classmethod
    def c(cls, code, text):
        return f"\033[{code}m{text}\033[0m" if cls.on else text
    @classmethod
    def green(cls, t): return cls.c("32", t)
    @classmethod
    def red(cls, t): return cls.c("31", t)
    @classmethod
    def dim(cls, t): return cls.c("2", t)
    @classmethod
    def bold(cls, t): return cls.c("1", t)
    @classmethod
    def yellow(cls, t): return cls.c("33", t)


def fever_bar(s, width=30):
    total = s["green"] + s["red"]
    if not total:
        return C.dim("░" * width)
    fill = round(width * s["green"] / total)
    return C.green("█" * fill) + C.red("░" * (width - fill))


def render(s, buffs, final):
    mins = duration_minutes(s)
    dur = f"{mins // 60}h {mins % 60}m" if mins else "unknown"
    date = (s["first_ts"] or "")[:10]
    models = meta_names(s["models"])
    efforts = meta_names(s["efforts"])
    w = 62
    line = "─" * w
    out = []
    out.append(C.dim("┌" + line + "┐"))
    out.append(C.bold("  LLM GRADER") + C.dim(f"  ·  session {s['session_id'][:8]}  ·  {date}  ·  {dur}  ·  {division(s)}"))
    out.append(C.dim(f"  {models}  ·  effort: {efforts}"))
    dn = delegation_note(s)
    if dn:
        out.append(C.dim(f"  {dn}"))
    out.append(C.dim("├" + line + "┤"))
    out.append("  " + fever_bar(s) + C.dim("  fever"))
    unknown = f"   ?{s['unknown_results']} unknown" if s.get("unknown_results") else ""
    out.append(C.green(f"  +{s['green']} green results") + "   " + C.red(f"-{s['red']} errors")
               + "   " + C.yellow(f"streak {s['longest_streak']}") + C.dim(unknown))
    ft, lt = s["first_tally"], s["last_tally"]
    if ft and lt:
        out.append(C.red(f"  - # {ft[0]} passed, {ft[1]} failed"))
        out.append(C.green(f"  + # {lt[0]} passed, {lt[1]} failed"))
    tool_bits = "  ".join(f"{k}:{v}" for k, v in sorted(s["tools"].items(), key=lambda kv: -kv[1])[:6])
    out.append(C.dim(f"  {tool_bits}"))
    if s["tokens_in"] or s["tokens_out"]:
        out.append(C.dim(f"  tokens: {s['tokens_in']/1e6:,.1f}M in · {s['tokens_out']/1e6:,.2f}M out"))
    out.append(C.dim("├" + line + "┤"))
    for name, kind, value, why in buffs:
        glyph = ICONS.get(name, "·")
        if kind == "flavor":
            tag = C.dim(f"+{value}")
        elif value >= 1:
            tag = C.green(f"×{round(value, 2)}")
        else:
            tag = C.red(f"×{value}")
        out.append(f"  {C.yellow(glyph) if kind == 'chain' else C.dim(glyph)} {C.bold(name):<38} {tag}  {C.dim(why)}")
    out.append(C.dim("├" + line + "┤"))
    core, flat = score_parts(s, buffs)
    out.append(C.bold(f"  FINAL: {C.yellow(f'+{final:,}')}")
               + C.dim(f"  (skill {core:,} · comedy {flat:,} · means nothing. share it anyway.)"))
    out.append(C.dim(f"  {SCORING_VERSION} · adapter {s.get('harness', 'claude-code')} · {fingerprint(s)}"))
    out.append(C.dim("└" + line + "┘"))
    return "\n".join(out)


def fingerprint(s):
    """Verification stamp: recomputing with the official script on the same
    transcript must reproduce the score. Detects edited numbers and modified
    scoring code; does not prove the transcript itself is genuine."""
    code = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:8]
    return f"recompute: transcript {s['transcript_sha'][:12]} · code {code}"


def render_html(s, buffs, final):
    """Standalone shareable card. Same field allowlist as the ANSI card."""
    mins = duration_minutes(s)
    dur = f"{mins // 60}h {mins % 60}m" if mins else "unknown"
    date = (s["first_ts"] or "")[:10]
    models = meta_names(s["models"])
    efforts = meta_names(s["efforts"])
    total = s["green"] + s["red"]
    pct = round(100 * s["green"] / total) if total else 0
    esc = html_mod.escape

    def chip(name, kind, value, why):
        glyph = ICONS.get(name, "·")
        tag = (f"+{value}" if kind == "flavor" else f"&times;{round(value, 2)}")
        art = badge_data_uri(name)
        tile = (f'<img class="tile art" src="{art}" alt="">' if art
                else f'<span class="tile">{esc(glyph)}</span>')
        return (f'<div class="badge {esc(kind)}">{tile}'
                f'<span class="bmeta"><span class="brow"><span class="bname">{esc(name)}</span>'
                f'<span class="btag">{tag}</span></span>'
                f'<span class="bwhy">{esc(why)}</span></span></div>')
    rows = ('<div class="badges">'
            + "".join(chip(*b) for b in buffs)
            + '</div>')
    tally = ""
    if s["first_tally"] and s["last_tally"]:
        ft, lt = s["first_tally"], s["last_tally"]
        tally = (f'<div class="diff"><div class="rm">- # {ft[0]} passed, {ft[1]} failed</div>'
                 f'<div class="add">+ # {lt[0]} passed, {lt[1]} failed</div></div>')
    tokens = ""
    if s["tokens_in"] or s["tokens_out"]:
        tokens = f'<div class="meta">tokens: {s["tokens_in"]/1e6:,.1f}M in &middot; {s["tokens_out"]/1e6:,.2f}M out</div>'
    core, flat = score_parts(s, buffs)
    return f"""<!-- llm-grader shareable card -->
<meta charset="utf-8">
<div style="max-width:560px">
<style>
.lg-card{{font-family:'SF Mono',Menlo,monospace;background:#0d1117;color:#c9d1d9;border:1px solid #30363d;border-radius:10px;padding:20px 24px;font-size:13px;line-height:1.7}}
.lg-card h1{{font-size:15px;margin:0;color:#e6edf3}}.lg-card .meta{{color:#8b949e;font-size:12px}}
.lg-card .fever{{height:10px;border-radius:5px;background:#f85149;overflow:hidden;margin:12px 0}}
.lg-card .fever i{{display:block;height:100%;width:{pct}%;background:#3fb950}}
.lg-card .counts{{margin:4px 0}}.lg-card .g{{color:#3fb950}}.lg-card .r{{color:#f85149}}.lg-card .y{{color:#d29922}}
.lg-card .diff{{margin:8px 0}}.lg-card .rm{{color:#f85149}}.lg-card .add{{color:#3fb950}}
.lg-card .badges{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:8px;margin:12px 0 4px}}
.lg-card .badge{{display:flex;gap:9px;align-items:center;border:1px solid #30363d;border-radius:7px;padding:7px 9px;background:#161b22}}
.lg-card .badge .tile{{flex:none;width:44px;height:44px;display:flex;align-items:center;justify-content:center;font-size:18px;border:1px solid #30363d;border-radius:8px;background:#0d1117;color:#8b949e}}
.lg-card .badge .tile.art{{object-fit:cover;padding:0}}
.lg-card .badge.chain{{border-color:#9e7c27;box-shadow:0 0 10px rgba(210,153,34,.18)}}
.lg-card .badge.chain .tile{{color:#d29922;border-color:#9e7c27}}
.lg-card .badge.chain .btag{{color:#d29922}}
.lg-card .badge.debuff{{border-color:#6e2c2f}}
.lg-card .badge.debuff .tile{{color:#f85149;border-color:#6e2c2f}}
.lg-card .badge.debuff .btag{{color:#f85149}}
.lg-card .badge.flavor .btag{{color:#8b949e}}
.lg-card .bmeta{{min-width:0;display:flex;flex-direction:column;gap:1px;flex:1}}
.lg-card .brow{{display:flex;justify-content:space-between;gap:8px;align-items:baseline}}
.lg-card .bname{{font-weight:700;color:#e6edf3;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.lg-card .btag{{font-weight:700;font-size:12px}}
.lg-card .bwhy{{color:#8b949e;font-size:10.5px;line-height:1.4}}
.lg-card .why{{color:#8b949e;font-size:12px}}
.lg-card .final{{margin-top:14px;border-top:1px solid #30363d;padding-top:10px;font-size:17px;color:#d29922;font-weight:700}}
.lg-card .fine{{color:#484f58;font-size:11px}}
</style>
<div class="lg-card">
<h1>LLM GRADER</h1>
<div class="meta">session {esc(s['session_id'][:8])} &middot; {esc(date)} &middot; {dur} &middot; {division(s)} &middot; {esc(models)} &middot; effort: {esc(efforts)}</div>
{f'<div class="meta">{esc(delegation_note(s))}</div>' if delegation_note(s) else ''}
<div class="fever"><i></i></div>
<div class="counts"><span class="g">+{s['green']} green results</span> &nbsp; <span class="r">-{s['red']} errors</span> &nbsp; <span class="y">streak {s['longest_streak']}</span></div>
{tally}{tokens}
{rows}
<div class="final">+{final:,} <span class="fine">(skill {core:,} &middot; comedy {flat:,} &middot; means nothing. share it anyway.)</span></div>
<div class="fine">{SCORING_VERSION} &middot; adapter {esc(s.get('harness', 'claude-code'))} &middot; {fingerprint(s)}</div>
</div></div>
"""


def projects_dir(override=None):
    """Transcript root: --projects-dir flag > $CLAUDE_CONFIG_DIR/projects > default."""
    if override:
        return Path(override).expanduser()
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return Path(env).expanduser() / "projects"
    return PROJECTS_DIR


def share_caption(s, buffs, final):
    """Suggested post text from allowlisted fields only. Copied locally; the
    user pastes and posts — the score never rides a URL to anyone's server."""
    core, flat = score_parts(s, buffs)
    top = " · ".join(f"{ICONS.get(n, '·')} {n}" for n, k, v, _ in buffs[:3])
    return (f"LLM Grader: +{final:,} (skill {core:,} · comedy {flat:,}) — {division(s)}\n"
            f"{top}\n(means nothing. sharing it anyway.) #LLMGrader")


def find_session(arg, root=None):
    if arg and Path(arg).exists():
        return Path(arg)
    base = root or PROJECTS_DIR
    candidates = sorted(base.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if arg:  # partial uuid match
        for p in candidates:
            if p.stem.startswith(arg):
                return p
        sys.exit(f"no session matching '{arg}' under {base}")
    if not candidates:
        sys.exit(f"no session transcripts found under {base}")
    return candidates[0]


def main():
    ap = argparse.ArgumentParser(description="Grade a Claude Code session into a comedy results card (local-only, zero-upload).")
    ap.add_argument("session", nargs="?", help="Path to a session .jsonl, a session-uuid prefix, or omit for the most recent session")
    ap.add_argument("--html", nargs="?", const="", metavar="OUT",
                    help="Also write a shareable standalone HTML card (default: ./llm-grader-card-<id>.html)")
    ap.add_argument("--share", action="store_true",
                    help="Copy a suggested post caption to the clipboard and open a blank X composer. Nothing is transmitted; you paste and post.")
    ap.add_argument("--projects-dir", metavar="DIR",
                    help="Transcript root (default: $CLAUDE_CONFIG_DIR/projects or ~/.claude/projects)")
    args = ap.parse_args()
    path = find_session(args.session, projects_dir(args.projects_dir))
    s = analyze(path)
    buffs = pick_buffs(s)
    final = score(s, buffs)
    print(render(s, buffs, final))
    if args.html is not None:
        out = Path(args.html) if args.html else Path(f"llm-grader-card-{s['session_id'][:8]}.html")
        out.write_text(render_html(s, buffs, final))
        print(f"\nhtml card: {out.resolve()}")
    if args.share:
        caption = share_caption(s, buffs, final)
        print("\nsuggested caption:\n" + caption)
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=caption.encode(), check=False)
            print("(copied to clipboard)")
            subprocess.run(["open", "https://x.com/compose/post"], check=False)


if __name__ == "__main__":
    main()
