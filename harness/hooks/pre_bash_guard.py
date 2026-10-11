#!/usr/bin/env python3
"""PreToolUse(Bash): enforce the bounds that were prose-only and broke in the 2026-10-04..11 audit.

Always blocked (safety, from TEAM-OPS-style working agreements):
  - git commit --no-verify / -n
  - force pushes; pushing the default branch
  - rewriting the gate or git hooks through a shell redirect
Bounds (numbers from docs/agents/harness.toml):
  - sleep-polling: `sleep N` with N >= 30, or a loop around sleep. Waiting is one blocking wait
    on the child (background-agent notification / Monitor / process wait). Cue 2026-10-05:
    153 sleep loops past the 5-minute cache TTL rewrote 24M cache tokens.
  - full suite: more than [bounds].full_suite_per_loop runs of [gate].full_suite per agent.
    Escape hatch for a deliberate rerun: prefix the command with FULL_SUITE_OK=<reason>.
"""
import re
import shlex

from _common import actor_id, block, counter, project, read_payload, run_log
import harness_config  # noqa: E402  (path set by _common)

payload = read_payload()
cfg = project(payload)
if not cfg:
    raise SystemExit(0)
cmd = (payload.get("tool_input") or {}).get("command") or ""
segments = re.split(r"[|;&\n]+", cmd)

SAFETY = [
    (r"\bgit\b.*\bcommit\b.*(\s--no-verify\b|\s-n\b)", "git commit --no-verify is forbidden: fix the gate failure instead"),
    (r"\bgit\b.*\bpush\b.*(\s--force\b|\s-f\b|\s--force-with-lease\b)", "force pushes are forbidden"),
    (r"\bgit\b.*\bpush\b.*\b(origin\s+)?(HEAD:)?(main|master)\b", "pushing the default branch is forbidden (PRs only)"),
    (r"(>|>>|\btee\b)\s*\S*(\.githooks/|review-gate\.sh)", "do not rewrite the gate or git hooks from a shell redirect"),
]
for seg in segments:
    for pat, why in SAFETY:
        if re.search(pat, seg):
            block(why)

if re.search(r"\bsleep\s+(\d{3,}|[3-9]\d)\b", cmd) or re.search(r"\b(while|until)\b.*\bsleep\b", cmd, re.S):
    run_log(cfg, f"blocked sleep-poll: {cmd[:80]!r}")
    block("polling with sleep is not allowed: take one blocking wait on the child "
          "(background agent notification, Monitor, or wait on the process). "
          "Sleeping past 5 minutes also expires the prompt cache and re-bills the whole context.")

full = harness_config.get(cfg, "gate.full_suite", "")
limit = int(harness_config.get(cfg, "bounds.full_suite_per_loop", 1))
if full and "FULL_SUITE_OK=" not in cmd:
    want = shlex.split(full)
    for seg in segments:
        try:
            got = shlex.split(seg.strip())
        except ValueError:
            continue
        if got[: len(want)] == want and len(got) == len(want):
            n = counter("fullsuite", actor_id(payload))
            if n > limit:
                run_log(cfg, f"blocked full suite #{n}: {full}")
                block(f"the full suite ({full}) already ran {limit}x for this agent this loop. Run focused "
                      f"tests, or prefix FULL_SUITE_OK=<reason> if this rerun is deliberate.")
raise SystemExit(0)
