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

SCORING_VERSION = "scoring-v0.1 (entertainment only)"
PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Known-format tally parsing (non-semantic; fails open on no-match).
TALLY_RE = re.compile(r"(\d+)\s+passed(?:,?\s+(\d+)\s+fail(?:ed|ures?))?", re.IGNORECASE)
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
    }
    streak = spiral = 0
    for rec in iter_records(path):
        ts = rec.get("timestamp")
        if ts:
            s["first_ts"] = s["first_ts"] or ts
            s["last_ts"] = ts
        rtype = rec.get("type")
        if rtype == "assistant":
            model = (rec.get("message") or {}).get("model")
            if model and not model.startswith("<"):
                s["models"][model] = s["models"].get(model, 0) + 1
            effort = rec.get("effort")
            if effort:
                s["efforts"][effort] = s["efforts"].get(effort, 0) + 1
            for block in (rec.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    s["tools"][name] = s["tools"].get(name, 0) + 1
        elif rtype == "user":
            content = (rec.get("message") or {}).get("content")
            if isinstance(content, str):
                s["user_prompts"] += 1
                if INTERRUPT_MARKER in content:
                    s["interruptions"] += 1
                continue
            if not isinstance(content, list):
                continue
            saw_tool_result = False
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and INTERRUPT_MARKER in block.get("text", ""):
                    s["interruptions"] += 1
                if block.get("type") != "tool_result":
                    continue
                saw_tool_result = True
                if block.get("is_error"):
                    s["red"] += 1
                    spiral += 1
                    s["worst_spiral"] = max(s["worst_spiral"], spiral)
                    streak = 0
                else:
                    s["green"] += 1
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
        elif rtype == "system" and "compact" in str(rec.get("subtype", "")).lower():
            s["compactions"] += 1
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
    reads, bashes = tools.get("Read", 0), tools.get("Bash", 0)
    if bashes >= 30 and reads < bashes // 5:
        buffs.append(("YOLO Ops", 1.1, f"{bashes} commands, barely read a thing"))
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
    out.append(C.dim("├" + line + "┤"))
    for name, mult, why in buffs:
        tag = C.green(f"×{mult}") if mult >= 1 else C.red(f"×{mult}")
        out.append(f"  {C.bold(name):<38} {tag}  {C.dim(why)}")
    out.append(C.dim("├" + line + "┤"))
    out.append(C.bold(f"  FINAL: {C.yellow(f'+{final:,}')}") + C.dim("  (means nothing. share it anyway.)"))
    out.append(C.dim(f"  {SCORING_VERSION}"))
    out.append(C.dim("└" + line + "┘"))
    return "\n".join(out)


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
    args = ap.parse_args()
    path = find_session(args.session)
    s = analyze(path)
    buffs = pick_buffs(s)
    print(render(s, buffs, score(s, buffs)))


if __name__ == "__main__":
    main()
