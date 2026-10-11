#!/usr/bin/env python3
"""PreToolUse(Agent): model routing and the broad-review cap, read from docs/agents/harness.toml.

Claude Code's subagent tool is `Agent`; Codex's spawn_agent also matches `Agent`.
Briefs written by harness-orchestrator start with two header lines:
    Role: <tiers key>        e.g. implementer, reviewer_first, merge_resolver
    Ticket: <id>
A spawn above its role's tier is logged and allowed in `warn` mode (the default while rolling
out) and blocked in `block` mode, unless the brief carries `tier-override: <reason>`.
The broad-review cap ([bounds].broad_reviews per ticket) always blocks: PZL-98 ran 9 rounds.
"""
import re

from _common import block, counter, project, read_payload, run_log
import harness_config  # noqa: E402  (path set by _common)

RANK = {"mechanical": 0, "default": 1, "frontier": 2}
payload = read_payload()
cfg = project(payload)
if not cfg:
    raise SystemExit(0)
ti = payload.get("tool_input") or {}
brief = str(ti.get("prompt") or ti.get("message") or ti.get("task") or "")
role = (re.search(r"^\s*Role:\s*([\w-]+)", brief, re.M) or [None, None])[1]
ticket = (re.search(r"^\s*Ticket:\s*([\w-]+)", brief, re.M) or [None, None])[1]
if not role:
    raise SystemExit(0)  # not a harness spawn (ad-hoc research, Explore, etc.)
role = role.replace("-", "_")

if role == "reviewer_first" and ticket:
    cap = int(harness_config.get(cfg, "bounds.broad_reviews", 2))
    key = f"{cfg['_root']}-{ticket}"
    if counter("broadreview", key, bump=False) >= cap:
        run_log(cfg, f"blocked broad review #{cap + 1} for {ticket}")
        block(f"{ticket} already had {cap} broad reviews. Use targeted verify of the open finding ids "
              f"with the same reviewer (Role: reviewer_verify).")
    counter("broadreview", key)

tool = "codex" if "spawn_agent" in str(payload.get("tool_name", "")) or payload.get("turn_id") else "claude"
want_tier = harness_config.get(cfg, f"tiers.{role}")
models = harness_config.get(cfg, f"models.{tool}", {}) or {}
asked = ti.get("model")
asked_tier = next((t for t, m in models.items() if asked and str(asked).startswith(str(m))), None)
if want_tier and asked_tier and RANK.get(asked_tier, 1) > RANK.get(want_tier, 1) and "tier-override:" not in brief:
    msg = f"{role} for {ticket or '?'} asked for {asked} ({asked_tier}); harness.toml routes it to {want_tier} ({models.get(want_tier)})"
    run_log(cfg, f"over-tier spawn: {msg}")
    if harness_config.get(cfg, "enforce.tiers", "warn") == "block":
        block(msg + ". Spawn at the routed tier, or add `tier-override: <reason>` to the brief.")
raise SystemExit(0)
