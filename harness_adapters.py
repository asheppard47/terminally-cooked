#!/usr/bin/env python3
"""Harness adapters: route-by-harness session ingestion for Terminally Cooked.

Each adapter reads LOCAL files only and normalizes a session into the shared
event contract consumed by grade_session.analyze_events(). Detection is
content-first (sniff the schema), path-second, and never trusts a flag.
Design: docs/design/harness-adapters.md. Schemas verified against real local
session stores on 2026-08-20; anything absent in a harness simply never emits
its event (detectors fail open).

Normalized events (dicts; every event may carry "ts" ISO-8601):
  {"kind": "human"}                                   user turn
  {"kind": "interrupt"}                               user interrupted the agent
  {"kind": "tool_call", "id", "name", "command"}      command may be None
  {"kind": "tool_result", "id", "success", "text"}    success: True|False|None
  {"kind": "model", "model", "effort"}                either field may be None
  {"kind": "usage", "input", "output"}                token counts
  {"kind": "permission", "mode"}                      "bypass" | "plan"
  {"kind": "compaction"}
"""
import json
import re
from pathlib import Path

CLAUDE_INTERRUPT = "[Request interrupted"
EXIT_CODE_RE = re.compile(r"Exit code:\s*(-?\d+)")


def _iter_jsonl(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _text(content):
    """Flatten a string / list-of-text-blocks content field."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(x.get("text", "") for x in content if isinstance(x, dict))
    return ""


# ---------------------------------------------------------------- detection

CODEX_ENVELOPE = {"session_meta", "turn_context", "response_item", "event_msg",
                  "compacted", "world_state"}
CLAUDE_TYPES = {"last-prompt", "mode", "permission-mode", "user", "assistant",
                "attachment", "summary", "file-history-snapshot"}


def detect_harness(path):
    """Return 'claude-code' | 'codex' | 'grok' | 'gemini' | None.

    Content-first: sniff up to the first few parseable records (BOM- and
    blank-line-tolerant), then fall back to home-directory shape."""
    p = Path(path)
    if p.is_dir():
        if (p / "summary.json").exists() and (
                (p / "events.jsonl").exists() or (p / "updates.jsonl").exists()):
            return "grok"
        return None
    if p.suffix != ".jsonl":
        return None
    records = []
    try:
        with p.open(encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(records) >= 5:
                    break
    except OSError:
        return None
    for first in records:
        if not isinstance(first, dict):
            continue
        if first.get("type") in CODEX_ENVELOPE and "payload" in first:
            return "codex"
        if "sessionId" in first and "projectHash" in first:
            return "gemini"
        # Claude Code's giveaway is its record vocabulary or its home.
        if "parentUuid" in first or first.get("type") in CLAUDE_TYPES:
            return "claude-code"
    parent = str(p.parent)
    if ".claude" in parent:
        return "claude-code"
    if ".gemini" in parent:
        return "gemini"
    if ".codex" in parent:
        return "codex"
    return None


def session_identity(path, harness):
    """(session_id, bytes-for-hash-path). Grok sessions hash events.jsonl."""
    p = Path(path)
    if harness == "grok":
        return p.name, (p / "events.jsonl" if (p / "events.jsonl").exists()
                        else p / "updates.jsonl")
    if harness == "codex":
        return p.stem[-36:], p           # rollout-<ts>-<uuid>
    return p.stem, p


# ---------------------------------------------------------------- claude-code

def _claude_events(path):
    for rec in _iter_jsonl(path):
        ts = rec.get("timestamp")
        rtype = rec.get("type")
        if rec.get("isCompactSummary"):
            yield {"kind": "compaction", "ts": ts}
        if rtype == "permission-mode":
            mode = str(rec.get("permissionMode", ""))
            if mode == "bypassPermissions":
                yield {"kind": "permission", "mode": "bypass", "ts": ts}
            elif mode == "plan":
                yield {"kind": "permission", "mode": "plan", "ts": ts}
        elif rtype == "assistant":
            msg = rec.get("message") or {}
            model = msg.get("model")
            if model and not model.startswith("<"):
                yield {"kind": "model", "model": model,
                       "effort": rec.get("effort"), "ts": ts}
            usage = msg.get("usage") or {}
            if usage:
                yield {"kind": "usage", "ts": ts,
                       "input": (usage.get("input_tokens", 0)
                                 + usage.get("cache_read_input_tokens", 0)
                                 + usage.get("cache_creation_input_tokens", 0)),
                       "output": usage.get("output_tokens", 0)}
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    cmd = None
                    if block.get("name") == "Bash":
                        c = (block.get("input") or {}).get("command")
                        cmd = c.strip() if isinstance(c, str) else None
                    yield {"kind": "tool_call", "id": block.get("id"),
                           "name": block.get("name", "?"), "command": cmd, "ts": ts}
        elif rtype == "user":
            content = (rec.get("message") or {}).get("content")
            if isinstance(content, str):
                yield {"kind": "human", "ts": ts}
                if CLAUDE_INTERRUPT in content:
                    yield {"kind": "interrupt", "ts": ts}
                continue
            if not isinstance(content, list):
                continue
            saw_result = False
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    yield {"kind": "human", "ts": ts}
                    if CLAUDE_INTERRUPT in block.get("text", ""):
                        yield {"kind": "interrupt", "ts": ts}
                if block.get("type") != "tool_result":
                    continue
                saw_result = True
                yield {"kind": "tool_result", "id": block.get("tool_use_id"),
                       "success": not block.get("is_error"),
                       "text": _text(block.get("content")), "ts": ts}
            if not saw_result and not any(
                    isinstance(b, dict) and b.get("type") == "text" for b in content):
                yield {"kind": "human", "ts": ts}


# ---------------------------------------------------------------- codex

def _codex_success(text):
    m = EXIT_CODE_RE.search(text)
    if m:
        return int(m.group(1)) == 0
    return None            # tri-state: no universal error boolean in rollouts


def _codex_command(p):
    """Extract a command string from either call shape. custom_tool_call carries
    a raw input string; function_call packs JSON arguments."""
    if isinstance(p.get("input"), str):
        return p["input"]
    args = p.get("arguments")
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except json.JSONDecodeError:
            return None
        for key in ("command", "cmd", "script"):
            v = parsed.get(key) if isinstance(parsed, dict) else None
            if isinstance(v, str):
                return v
            if isinstance(v, list):
                return " ".join(str(x) for x in v)
    return None


def _codex_events(path):
    last_totals = None       # token_count records are cumulative snapshots:
    last_totals_ts = None    # summing per-snapshot usage double-counts turns
    for rec in _iter_jsonl(path):
        ts = rec.get("timestamp")
        rtype = rec.get("type")
        p = rec.get("payload") or {}
        if rtype == "compacted":
            yield {"kind": "compaction", "ts": ts}
        elif rtype == "turn_context":
            if p.get("model") or p.get("effort"):
                yield {"kind": "model", "model": p.get("model"),
                       "effort": p.get("effort"), "ts": ts}
            sandbox = json.dumps(p.get("sandbox_policy", "")).lower()
            if p.get("approval_policy") == "never" and (
                    "danger" in sandbox or "full" in sandbox):
                yield {"kind": "permission", "mode": "bypass", "ts": ts}
            collab = p.get("collaboration_mode") or {}
            if isinstance(collab, dict) and collab.get("kind") == "plan":
                yield {"kind": "permission", "mode": "plan", "ts": ts}
        elif rtype == "event_msg":
            st = p.get("type")
            if st == "user_message":
                yield {"kind": "human", "ts": ts}
            elif st == "turn_aborted":
                yield {"kind": "interrupt", "ts": ts}
            elif st == "token_count":
                tot = (p.get("info") or {}).get("total_token_usage") or {}
                if tot:
                    last_totals, last_totals_ts = tot, ts
        elif rtype == "response_item":
            st = p.get("type")
            if st == "message" and p.get("role") == "user":
                # current rollouts may carry user turns only here
                yield {"kind": "human", "ts": ts}
            elif st in ("function_call", "custom_tool_call"):
                yield {"kind": "tool_call", "id": p.get("call_id"),
                       "name": p.get("name", "?"),
                       "command": _codex_command(p), "ts": ts}
            elif st in ("function_call_output", "custom_tool_call_output"):
                text = _text(p.get("output"))
                yield {"kind": "tool_result", "id": p.get("call_id"),
                       "success": _codex_success(text), "text": text, "ts": ts}
    if last_totals:
        # input_tokens already includes cached tokens (total == input + output)
        yield {"kind": "usage", "ts": last_totals_ts,
               "input": last_totals.get("input_tokens", 0) or 0,
               "output": last_totals.get("output_tokens", 0) or 0}


# ---------------------------------------------------------------- grok

GROK_OUTCOME = {"success": True, "error": False, "invalid_tool": False,
                "hook_denied": False}


def _grok_events(path):
    d = Path(path)
    ev = d / "events.jsonl"
    if ev.exists():
        for rec in _iter_jsonl(ev):
            ts = rec.get("ts")
            rtype = rec.get("type")
            if rtype == "turn_started":
                yield {"kind": "human", "ts": ts}
                if rec.get("model_id"):
                    yield {"kind": "model", "model": rec.get("model_id"),
                           "effort": None, "ts": ts}
                if rec.get("yolo_mode"):
                    yield {"kind": "permission", "mode": "bypass", "ts": ts}
            elif rtype == "interjected":
                yield {"kind": "interrupt", "ts": ts}
            elif rtype == "tool_completed":
                yield {"kind": "tool_call", "id": rec.get("tool_call_id"),
                       "name": rec.get("tool_name", "?"), "command": None, "ts": ts}
                yield {"kind": "tool_result", "id": rec.get("tool_call_id"),
                       "success": GROK_OUTCOME.get(rec.get("outcome")),
                       "text": "", "ts": ts}
    up = d / "updates.jsonl"
    if up.exists():
        for rec in _iter_jsonl(up):
            u = rec
            if isinstance(rec.get("params"), dict):        # raw ACP notification
                u = rec["params"].get("update") or rec["params"]
            if isinstance(u, dict) and u.get("sessionUpdate") == "turn_completed":
                usage = u.get("usage") or {}
                if usage:
                    yield {"kind": "usage", "ts": None,
                           "input": (usage.get("inputTokens", 0)
                                     + usage.get("cachedReadTokens", 0)),
                           "output": usage.get("outputTokens", 0)}
    cc = d / "compaction_checkpoints"
    if cc.is_dir() and any(cc.iterdir()):
        yield {"kind": "compaction", "ts": None}


# ---------------------------------------------------------------- gemini

GEMINI_STATUS = {"success": True, "completed": True, "confirmed": True,
                 "error": False, "failed": False, "cancelled": None}


def _gemini_events(path):
    called = set()       # call ids whose tool_call was emitted
    resolved = set()     # call ids whose TERMINAL result was emitted
    anon = 0
    for rec in _iter_jsonl(path):
        if "$set" in rec or ("sessionId" in rec and "projectHash" in rec):
            continue
        ts = rec.get("timestamp")
        rtype = rec.get("type")
        if rtype == "user":
            yield {"kind": "human", "ts": ts}
        elif rtype == "gemini":
            if rec.get("model"):
                yield {"kind": "model", "model": rec.get("model"),
                       "effort": None, "ts": ts}
            tok = rec.get("tokens") or {}
            if tok:
                yield {"kind": "usage", "ts": ts,
                       "input": (tok.get("input") or 0) + (tok.get("cached") or 0),
                       "output": tok.get("output") or 0}
            for call in rec.get("toolCalls") or []:
                cid = call.get("id")
                if cid is None:
                    anon += 1
                    cid = f"_anon_{anon}"
                status = str(call.get("status") or "").lower()
                # records repeat with the same message id as calls progress;
                # emit the call once, and the result only on a TERMINAL status
                # ("running"/"pending" must not lock the outcome as unknown)
                if cid not in called:
                    called.add(cid)
                    args = call.get("args") or {}
                    cmd = args.get("command") if isinstance(args.get("command"), str) else None
                    yield {"kind": "tool_call", "id": cid,
                           "name": call.get("name", "?"), "command": cmd, "ts": ts}
                if status in GEMINI_STATUS and cid not in resolved:
                    resolved.add(cid)
                    yield {"kind": "tool_result", "id": cid,
                           "success": GEMINI_STATUS[status],
                           "text": _text(call.get("resultDisplay")), "ts": ts}


ADAPTERS = {"claude-code": _claude_events, "codex": _codex_events,
            "grok": _grok_events, "gemini": _gemini_events}


def iter_events(path, harness=None):
    harness = harness or detect_harness(path)
    if harness not in ADAPTERS:
        raise ValueError(f"unrecognized session format: {path}")
    return ADAPTERS[harness](path)
