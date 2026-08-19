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
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCORING_VERSION = "scoring-v0.2 (entertainment only)"
PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Known-format tally parsing (non-semantic; fails open on no-match).
TALLY_RE = re.compile(r"(\d+)\s+passed(?:,?\s+(\d+)\s+fail(?:ed|ures?))?", re.IGNORECASE)
OVERLOAD_RE = re.compile(r"overloaded|\b529\b", re.IGNORECASE)
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


def analyze(path):
    s = {
        "session_id": Path(path).stem,
        "models": {},
        "efforts": {},
        "tools": {},
        "green": 0,
        "red": 0,
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
    }
    streak = spiral = cook = 0
    pending_bash = {}   # tool_use id -> command string (never rendered)
    last_failed_cmd, doom_run = None, 0
    for rec in iter_records(path):
        ts = rec.get("timestamp")
        if ts:
            s["first_ts"] = s["first_ts"] or ts
            s["last_ts"] = ts
            try:
                hour = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().hour
                if 2 <= hour < 6:
                    s["night_events"] += 1
            except ValueError:
                pass
        if rec.get("isCompactSummary"):
            s["compactions"] += 1
        rtype = rec.get("type")
        if rtype == "permission-mode":
            mode = str(rec.get("permissionMode", ""))
            if mode == "bypassPermissions":
                s["yolo_mode"] = True
            elif mode == "plan":
                s["plan_entries"] += 1
        elif rtype == "assistant":
            msg = rec.get("message") or {}
            model = msg.get("model")
            if model and not model.startswith("<"):
                s["models"][model] = s["models"].get(model, 0) + 1
            effort = rec.get("effort")
            if effort:
                s["efforts"][effort] = s["efforts"].get(effort, 0) + 1
            usage = msg.get("usage") or {}
            s["tokens_in"] += (usage.get("input_tokens", 0)
                               + usage.get("cache_read_input_tokens", 0)
                               + usage.get("cache_creation_input_tokens", 0))
            s["tokens_out"] += usage.get("output_tokens", 0)
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    s["tools"][name] = s["tools"].get(name, 0) + 1
                    cook += 1
                    s["longest_cook"] = max(s["longest_cook"], cook)
                    if name == "Bash":
                        cmd = (block.get("input") or {}).get("command")
                        if isinstance(cmd, str):
                            pending_bash[block.get("id")] = cmd.strip()
        elif rtype == "user":
            content = (rec.get("message") or {}).get("content")
            if isinstance(content, str):
                s["user_prompts"] += 1
                cook = 0
                if INTERRUPT_MARKER in content:
                    s["interruptions"] += 1
                continue
            if not isinstance(content, list):
                continue
            saw_tool_result = False
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    cook = 0
                    if INTERRUPT_MARKER in block.get("text", ""):
                        s["interruptions"] += 1
                if block.get("type") != "tool_result":
                    continue
                saw_tool_result = True
                cmd = pending_bash.pop(block.get("tool_use_id"), None)
                if block.get("is_error"):
                    s["red"] += 1
                    if OVERLOAD_RE.search(tool_result_text(block)):
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
                    if cmd is not None:
                        last_failed_cmd, doom_run = None, 0
                    streak += 1
                    s["longest_streak"] = max(s["longest_streak"], streak)
                    spiral = 0
                m = TALLY_RE.search(tool_result_text(block))
                if m:
                    tally = (int(m.group(1)), int(m.group(2) or 0))
                    s["first_tally"] = s["first_tally"] or tally
                    s["last_tally"] = tally
            if not saw_tool_result:
                s["user_prompts"] += 1
    return s


def duration_minutes(s):
    try:
        t0 = datetime.fromisoformat(s["first_ts"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(s["last_ts"].replace("Z", "+00:00"))
        return max(1, int((t1 - t0).total_seconds() // 60))
    except (AttributeError, ValueError, TypeError):
        return None


def pick_buffs(s):
    """The buff/debuff catalog. Multipliers are jokes, not measurement."""
    buffs = []  # (name, mult, line)
    total = s["green"] + s["red"]
    tools = s["tools"]
    mins = duration_minutes(s)

    if s["longest_streak"] >= 25:
        buffs.append(("FLOW STATE", 1.5, f"{s['longest_streak']} green results without a miss"))
    elif s["longest_streak"] >= 10:
        buffs.append(("Clean Streak", 1.2, f"{s['longest_streak']} in a row"))
    if s["red"] == 0 and total >= 20:
        buffs.append(("ONE-SHOT WONDER", 1.6, "an entire session, zero errors. suspicious."))
    if s["worst_spiral"] >= 4:
        buffs.append(("Error Spiral", 0.7, f"{s['worst_spiral']} consecutive faceplants"))
    elif s["worst_spiral"] == 3:
        buffs.append(("Third Time's the Charm", 0.9, "3 straight errors, then grace"))
    ft, lt = s["first_tally"], s["last_tally"]
    if ft and lt and lt[0] > ft[0]:
        buffs.append(("Test Whisperer", 1.3, f"{ft[0]} passed -> {lt[0]} passed"))
    if ft and lt and lt[1] > ft[1]:
        buffs.append(("Red Wedding", 0.6, f"failures went {ft[1]} -> {lt[1]}"))
    if s["compactions"] >= 1:
        buffs.append(("Lost the Tapes", 1.1, f"survived {s['compactions']} compaction(s); records incomplete"))
    if len(s["models"]) >= 3:
        buffs.append(("Model Hopper", 1.1, f"{len(s['models'])} different models in one session"))
    if tools.get("Agent", 0) >= 5:
        buffs.append(("Middle Manager", 1.2, f"delegated to {tools['Agent']} subagents"))
    if tools.get("AskUserQuestion", 0) >= 4:
        buffs.append(("Twenty Questions", 0.9, f"asked the human {tools['AskUserQuestion']} times"))
    if s["interruptions"] >= 3:
        buffs.append(("Backseat Driver", 0.8, f"human slammed the brakes {s['interruptions']} times"))
    # Research-backed entries (X sweep 2026-08-18; see llm-grader-concept.md)
    if s["yolo_mode"]:
        buffs.append(("YOLO MODE", 1.4, "--dangerously-skip-permissions. respect."))
    if s["longest_cook"] >= 50:
        buffs.append(("LET IT COOK", 1.3, f"{s['longest_cook']} tool calls without human input"))
    if s["tokens_in"] >= 100_000_000 or s["tokens_out"] >= 1_000_000:
        buffs.append(("Token Bonfire", 1.2, f"{s['tokens_in']/1e6:.0f}M tokens. the meter is spinning."))
    if s["plan_entries"] >= 1 and tools.get("Edit", 0) + tools.get("Write", 0) == 0:
        buffs.append(("All Plan No Game", 0.8, f"entered plan mode {s['plan_entries']}x, edited nothing"))
    if s["overloads"] >= 1:
        buffs.append(("Overloaded", 0.9, f"the API said no, {s['overloads']}x (rare)"))
    if s["worst_doom_loop"] >= 3:
        buffs.append(("Doom Loop", 0.7, f"same command, same failure, {s['worst_doom_loop']}x in a row"))
    if s["night_events"] >= 10:
        buffs.append(("Night Shift", 1.2, "real work happening between 2 and 6 am"))
    reads, bashes = tools.get("Read", 0), tools.get("Bash", 0)
    if reads >= 20 and reads > bashes:
        buffs.append(("Bookworm", 1.0, f"read {reads} files, touched grass never"))
    if mins and mins >= 240:
        buffs.append(("Marathon", 1.2, f"{mins // 60}h {mins % 60}m in the chair"))
    elif mins and mins <= 10 and total >= 10:
        buffs.append(("Speedrun", 1.4, f"in and out in {mins} minutes"))
    if not buffs:
        buffs.append(("Perfectly Balanced", 1.0, "as all things should be"))
    return buffs


def score(s, buffs):
    base = s["green"] * 10 - s["red"] * 15 + s["longest_streak"] * 5
    ft, lt = s["first_tally"], s["last_tally"]
    if ft and lt:
        base += (lt[0] - ft[0]) * 25
    mult = 1.0
    for _, m, _ in buffs:
        mult *= m
    return max(0, int(base * mult))


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
    models = ", ".join(sorted(s["models"], key=s["models"].get, reverse=True))
    efforts = ", ".join(sorted(s["efforts"], key=s["efforts"].get, reverse=True))
    w = 62
    line = "─" * w
    out = []
    out.append(C.dim("┌" + line + "┐"))
    out.append(C.bold("  LLM GRADER") + C.dim(f"  ·  session {s['session_id'][:8]}  ·  {date}  ·  {dur}"))
    out.append(C.dim(f"  {models}  ·  effort: {efforts}"))
    out.append(C.dim("├" + line + "┤"))
    out.append("  " + fever_bar(s) + C.dim("  fever"))
    out.append(C.green(f"  +{s['green']} green results") + "   " + C.red(f"-{s['red']} errors")
               + "   " + C.yellow(f"streak {s['longest_streak']}"))
    ft, lt = s["first_tally"], s["last_tally"]
    if ft and lt:
        out.append(C.red(f"  - # {ft[0]} passed, {ft[1]} failed"))
        out.append(C.green(f"  + # {lt[0]} passed, {lt[1]} failed"))
    tool_bits = "  ".join(f"{k}:{v}" for k, v in sorted(s["tools"].items(), key=lambda kv: -kv[1])[:6])
    out.append(C.dim(f"  {tool_bits}"))
    if s["tokens_in"] or s["tokens_out"]:
        out.append(C.dim(f"  tokens: {s['tokens_in']/1e6:,.1f}M in · {s['tokens_out']/1e6:,.2f}M out"))
    out.append(C.dim("├" + line + "┤"))
    for name, mult, why in buffs:
        tag = C.green(f"×{mult}") if mult >= 1 else C.red(f"×{mult}")
        out.append(f"  {C.bold(name):<38} {tag}  {C.dim(why)}")
    out.append(C.dim("├" + line + "┤"))
    out.append(C.bold(f"  FINAL: {C.yellow(f'+{final:,}')}") + C.dim("  (means nothing. share it anyway.)"))
    out.append(C.dim(f"  {SCORING_VERSION}"))
    out.append(C.dim("└" + line + "┘"))
    return "\n".join(out)


def render_html(s, buffs, final):
    """Standalone shareable card. Same field allowlist as the ANSI card."""
    mins = duration_minutes(s)
    dur = f"{mins // 60}h {mins % 60}m" if mins else "unknown"
    date = (s["first_ts"] or "")[:10]
    models = ", ".join(sorted(s["models"], key=s["models"].get, reverse=True))
    efforts = ", ".join(sorted(s["efforts"], key=s["efforts"].get, reverse=True))
    total = s["green"] + s["red"]
    pct = round(100 * s["green"] / total) if total else 0
    rows = "".join(
        f'<div class="buff"><span class="name">{name}</span>'
        f'<span class="mult {"up" if mult >= 1 else "down"}">&times;{mult}</span>'
        f'<span class="why">{why}</span></div>'
        for name, mult, why in buffs)
    tally = ""
    if s["first_tally"] and s["last_tally"]:
        ft, lt = s["first_tally"], s["last_tally"]
        tally = (f'<div class="diff"><div class="rm">- # {ft[0]} passed, {ft[1]} failed</div>'
                 f'<div class="add">+ # {lt[0]} passed, {lt[1]} failed</div></div>')
    tokens = ""
    if s["tokens_in"] or s["tokens_out"]:
        tokens = f'<div class="meta">tokens: {s["tokens_in"]/1e6:,.1f}M in &middot; {s["tokens_out"]/1e6:,.2f}M out</div>'
    return f"""<!-- llm-grader shareable card -->
<div style="max-width:560px">
<style>
.lg-card{{font-family:'SF Mono',Menlo,monospace;background:#0d1117;color:#c9d1d9;border:1px solid #30363d;border-radius:10px;padding:20px 24px;font-size:13px;line-height:1.7}}
.lg-card h1{{font-size:15px;margin:0;color:#e6edf3}}.lg-card .meta{{color:#8b949e;font-size:12px}}
.lg-card .fever{{height:10px;border-radius:5px;background:#f85149;overflow:hidden;margin:12px 0}}
.lg-card .fever i{{display:block;height:100%;width:{pct}%;background:#3fb950}}
.lg-card .counts{{margin:4px 0}}.lg-card .g{{color:#3fb950}}.lg-card .r{{color:#f85149}}.lg-card .y{{color:#d29922}}
.lg-card .diff{{margin:8px 0}}.lg-card .rm{{color:#f85149}}.lg-card .add{{color:#3fb950}}
.lg-card .buff{{display:flex;gap:10px;align-items:baseline;margin:3px 0}}
.lg-card .name{{font-weight:700;min-width:170px;color:#e6edf3}}
.lg-card .mult.up{{color:#3fb950}}.lg-card .mult.down{{color:#f85149}}
.lg-card .why{{color:#8b949e;font-size:12px}}
.lg-card .final{{margin-top:14px;border-top:1px solid #30363d;padding-top:10px;font-size:17px;color:#d29922;font-weight:700}}
.lg-card .fine{{color:#484f58;font-size:11px}}
</style>
<div class="lg-card">
<h1>LLM GRADER</h1>
<div class="meta">session {s['session_id'][:8]} &middot; {date} &middot; {dur} &middot; {models} &middot; effort: {efforts}</div>
<div class="fever"><i></i></div>
<div class="counts"><span class="g">+{s['green']} green results</span> &nbsp; <span class="r">-{s['red']} errors</span> &nbsp; <span class="y">streak {s['longest_streak']}</span></div>
{tally}{tokens}
{rows}
<div class="final">+{final:,} <span class="fine">(means nothing. share it anyway.)</span></div>
<div class="fine">{SCORING_VERSION}</div>
</div></div>
"""


def find_session(arg):
    if arg and Path(arg).exists():
        return Path(arg)
    candidates = sorted(PROJECTS_DIR.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if arg:  # partial uuid match
        for p in candidates:
            if p.stem.startswith(arg):
                return p
        sys.exit(f"no session matching '{arg}' under {PROJECTS_DIR}")
    if not candidates:
        sys.exit(f"no session transcripts found under {PROJECTS_DIR}")
    return candidates[0]


def main():
    ap = argparse.ArgumentParser(description="Grade a Claude Code session into a comedy results card (local-only, zero-upload).")
    ap.add_argument("session", nargs="?", help="Path to a session .jsonl, a session-uuid prefix, or omit for the most recent session")
    ap.add_argument("--html", nargs="?", const="", metavar="OUT",
                    help="Also write a shareable standalone HTML card (default: ./llm-grader-card-<id>.html)")
    args = ap.parse_args()
    path = find_session(args.session)
    s = analyze(path)
    buffs = pick_buffs(s)
    final = score(s, buffs)
    print(render(s, buffs, final))
    if args.html is not None:
        out = Path(args.html) if args.html else Path(f"llm-grader-card-{s['session_id'][:8]}.html")
        out.write_text(render_html(s, buffs, final))
        print(f"\nhtml card: {out.resolve()}")


if __name__ == "__main__":
    main()
