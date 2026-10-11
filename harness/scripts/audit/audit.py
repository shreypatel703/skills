#!/usr/bin/env python3
"""Run the agent-efficiency audit over a window.

Parses every Codex rollout (~/.codex/sessions) and Claude Code transcript
(~/.claude/projects/<this repo>*) whose activity falls in the window, strips imported
history and forked-thread replays, and writes the tables that the 2026-09-17/18 audit was
built from into --out. Read-only; nothing under the repo, ~/.claude or ~/.codex is modified.

Usage: audit.py --since 2026-09-17 [--until 2026-09-18T18:15] [--tz America/New_York] [--out .agent-audit/<since>]
Then read <out>/tables/*.md: analyze1 (totals by model/day), analyze2 (by ticket/phase,
top threads, cache, tier fit, thinking share), analyze3 (repeated work, orchestrator
overhead, idle), t6_reviews (review economics), t5_full_suite, t7_polling.
"""
import argparse, datetime as dt, os, pathlib, shutil, subprocess, sys
from zoneinfo import ZoneInfo

HERE = pathlib.Path(__file__).resolve().parent
STEPS = ["parse_codex.py", "parse_claude.py", "build_table.py", "extract_finals.py"]
TABLES = {"analyze1.py": "t1_totals.md", "analyze2.py": "analyze2.md", "analyze3.py": "analyze3.md",
          "review_econ.py": "t6_reviews.md", "fullsuite.py": "t5_full_suite.md", "poll_cost.py": "t7_polling.md"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", required=True); ap.add_argument("--until"); ap.add_argument("--tz", default="America/New_York")
    ap.add_argument("--out"); ap.add_argument("--self-session", default=os.environ.get("CLAUDE_SESSION_ID", ""))
    a = ap.parse_args()
    tz = ZoneInfo(a.tz)
    def parse(s, end=False):
        d = dt.datetime.fromisoformat(s)
        if len(s) == 10 and end: d = d.replace(hour=23, minute=59, second=59)
        return d.replace(tzinfo=tz).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    w0 = parse(a.since); w1 = parse(a.until, end=True) if a.until else dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = pathlib.Path(a.out or f".agent-audit/{a.since}").resolve()
    (out / "tables").mkdir(parents=True, exist_ok=True)
    for f in HERE.glob("*.py"):
        shutil.copy(f, out / f.name)
    repo = os.environ.get("AUDIT_REPO") or subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or str(HERE.parents[2])
    env = dict(os.environ, AUDIT_W0=w0, AUDIT_W1=w1, AUDIT_SELF_SESSION=a.self_session, AUDIT_REPO=repo)
    print(f"window {w0} .. {w1}  → {out}")
    for step in STEPS:
        r = subprocess.run([sys.executable, step], cwd=out, env=env, capture_output=True, text=True)
        print(f"  {step}: {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''}{(' ERR ' + r.stderr.strip()[-300:]) if r.returncode else ''}")
        if r.returncode: return 1
    for step, table in TABLES.items():
        r = subprocess.run([sys.executable, step], cwd=out, env=env, capture_output=True, text=True)
        (out / "tables" / table).write_text(r.stdout + (("\n<!-- stderr -->\n" + r.stderr) if r.returncode else ""))
    print("tables:", ", ".join(str(out / "tables" / t) for t in TABLES.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
