#!/usr/bin/env python3
"""Regression tests for grade_session.py against a synthetic fixture transcript."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from grade_session import analyze, pick_buffs, score, render_html

TS = "2026-08-19T03:{m:02d}:00.000Z"  # 03:xx UTC — hour depends on local tz; night test overrides


def asst(blocks, model="claude-sonnet-5", effort="high", ts="2026-08-19T10:00:00.000Z", usage=None):
    return {"type": "assistant", "timestamp": ts, "effort": effort,
            "message": {"model": model, "content": blocks, "usage": usage or {}}}


def tool_use(name, tid, **inp):
    return {"type": "tool_use", "name": name, "id": tid, "input": inp}


def result(tid, text="", err=False, ts="2026-08-19T10:01:00.000Z"):
    return {"type": "user", "timestamp": ts,
            "message": {"content": [{"type": "tool_result", "tool_use_id": tid,
                                     "is_error": err, "content": text}]}}


def prompt(text="do the thing", ts="2026-08-19T09:59:00.000Z"):
    return {"type": "user", "timestamp": ts, "message": {"content": text}}


def write_fixture(records):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for r in records:
        f.write(json.dumps(r) + "\n")
    f.close()
    return f.name


def buff_names(s):
    return {b[0] for b in pick_buffs(s)}


def test_basic_counts():
    recs = [prompt(),
            asst([tool_use("Bash", "t1", command="ls")]),
            result("t1", "ok"),
            asst([tool_use("Bash", "t2", command="pytest")]),
            result("t2", "12 passed, 3 failed"),
            asst([tool_use("Bash", "t3", command="pytest")]),
            result("t3", "15 passed, 0 failed"),
            asst([tool_use("Bash", "t4", command="bad")]),
            result("t4", "boom", err=True)]
    s = analyze(write_fixture(recs))
    assert s["green"] == 3 and s["red"] == 1, (s["green"], s["red"])
    assert s["longest_streak"] == 3
    assert s["first_tally"] == (12, 3) and s["last_tally"] == (15, 0)
    assert "Test Whisperer" in buff_names(s)


def test_doom_loop_same_command():
    recs = [prompt()]
    for i in range(3):
        recs.append(asst([tool_use("Bash", f"d{i}", command="make build")]))
        recs.append(result(f"d{i}", "error: no rule", err=True))
    s = analyze(write_fixture(recs))
    assert s["worst_doom_loop"] == 3, s["worst_doom_loop"]
    assert "Doom Loop" in buff_names(s)


def test_doom_loop_needs_identical_commands():
    recs = [prompt()]
    for i, cmd in enumerate(["make a", "make b", "make c"]):
        recs.append(asst([tool_use("Bash", f"d{i}", command=cmd)]))
        recs.append(result(f"d{i}", "err", err=True))
    s = analyze(write_fixture(recs))
    assert s["worst_doom_loop"] == 1
    assert "Doom Loop" not in buff_names(s)


def test_doom_loop_reset_by_success():
    recs = [prompt()]
    for i in range(2):
        recs.append(asst([tool_use("Bash", f"d{i}", command="make")]))
        recs.append(result(f"d{i}", "err", err=True))
    recs.append(asst([tool_use("Bash", "ok", command="make")]))
    recs.append(result("ok", "fine"))
    recs.append(asst([tool_use("Bash", "d9", command="make")]))
    recs.append(result("d9", "err", err=True))
    s = analyze(write_fixture(recs))
    assert s["worst_doom_loop"] == 2


def test_compaction_marker():
    recs = [prompt(),
            {"type": "user", "isCompactSummary": True, "timestamp": "2026-08-19T10:00:00.000Z",
             "message": {"content": [{"type": "text", "text": "summary"}]}}]
    recs += [asst([tool_use("Bash", f"g{i}", command="ls")]) for i in range(1)]
    recs += [result("g0", "ok")]
    s = analyze(write_fixture(recs))
    assert s["compactions"] == 1
    assert "Lost the Tapes" in buff_names(s)


def test_yolo_mode():
    recs = [{"type": "permission-mode", "permissionMode": "bypassPermissions"}, prompt()]
    s = analyze(write_fixture(recs))
    assert s["yolo_mode"] is True
    assert "YOLO MODE" in buff_names(s)


def test_let_it_cook():
    recs = [prompt()]
    for i in range(55):
        recs.append(asst([tool_use("Bash", f"c{i}", command=f"step {i}")]))
        recs.append(result(f"c{i}", "ok"))
    s = analyze(write_fixture(recs))
    assert s["longest_cook"] == 55
    assert "LET IT COOK" in buff_names(s)
    # a human text prompt resets the run
    recs.append(prompt("now stop"))
    recs.append(asst([tool_use("Bash", "z", command="ls")]))
    recs.append(result("z", "ok"))
    s2 = analyze(write_fixture(recs))
    assert s2["longest_cook"] == 55


def test_token_bonfire():
    recs = [prompt(), asst([tool_use("Bash", "t", command="ls")],
                           usage={"input_tokens": 10, "cache_read_input_tokens": 120_000_000,
                                  "output_tokens": 500}),
            result("t", "ok")]
    s = analyze(write_fixture(recs))
    assert s["tokens_in"] == 120_000_010
    assert "Token Bonfire" in buff_names(s)


def test_html_card_allowlist():
    recs = [prompt("SECRET-PROMPT-TEXT"),
            asst([tool_use("Bash", "t1", command="cat /Users/someone/secret/path.txt")]),
            result("t1", "SECRET-OUTPUT 5 passed")]
    s = analyze(write_fixture(recs))
    html = render_html(s, pick_buffs(s), score(s, pick_buffs(s)))
    for leak in ("SECRET-PROMPT-TEXT", "SECRET-OUTPUT", "secret/path", "/Users/"):
        assert leak not in html, f"card leaked: {leak}"


def test_score_floor():
    recs = [prompt()]
    for i in range(6):
        recs.append(asst([tool_use("Bash", f"e{i}", command="fail")]))
        recs.append(result(f"e{i}", "err", err=True))
    s = analyze(write_fixture(recs))
    assert score(s, pick_buffs(s)) == 0


def test_cli_smoke():
    recs = [prompt(), asst([tool_use("Bash", "t", command="ls")]), result("t", "ok")]
    fix = write_fixture(recs)
    out = subprocess.run([sys.executable, str(Path(__file__).parent / "grade_session.py"), fix],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "LLM GRADER" in out.stdout


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_")}.items()):
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL {name}: {e}")
    print(f"\n{'FAILED' if fails else 'OK'} — {fails} failures")
    sys.exit(1 if fails else 0)
