#!/usr/bin/env python3
"""Stop / SubagentStop: cost log, plus the question guard on the main agent's Stop.

Question guard. The 2026-10-04..11 audit found 14% of agent turns ending in a question, 8 of
them waiting more than 2 h, most asking permission for something already pre-authorised
("should I commit the spec?"). When the last message ends in a question:
  - it touches an item in [preauth].never  -> let the turn end and push a notification;
  - it asks to do something in [preauth].allowed -> block the stop once and tell the agent
    to proceed with its default and record the choice;
  - anything else (a real product or owner decision) -> let it end and push a notification.
`stop_hook_active` guards against a loop: a stop that was already blocked once always ends.

Both tools accept {"decision": "block", "reason": ...} on stdout. Codex wants JSON on stdout
for SubagentStop even when it allows, so this hook always prints one object.
"""
import json
import re
import sys
from pathlib import Path

from _common import notify, project, read_payload, run_log
import harness_config  # noqa: E402  (path set by _common)
from cost_log import log_usage

payload = read_payload()
cfg = project(payload)
out: dict = {}
if cfg:
    log_usage(payload, cfg)
    is_main = payload.get("hook_event_name") == "Stop"
    msg = (payload.get("last_assistant_message") or "").strip()
    tail = msg.splitlines()[-1].strip() if msg else ""
    if is_main and tail.endswith("?") and not payload.get("stop_hook_active"):
        q = tail.lower()
        hits = lambda key: any(re.search(p, q, re.I) for p in harness_config.get(cfg, key, []))
        hits_never = hits("preauth.never_patterns")
        ask_permission = re.search(r"\b(should i|shall i|do you want me to|want me to|ok to|okay to|can i|may i|proceed)\b", q)
        hits_allowed = hits("preauth.allowed_patterns")
        if ask_permission and hits_allowed and not hits_never:
            run_log(cfg, f"pre-authorised question auto-answered: {tail[:120]!r}")
            out = {"decision": "block", "reason": (
                "That is pre-authorised in docs/agents/harness.toml [preauth].allowed. Proceed with your "
                "default, record the choice in the PR body or ticket, and continue. Ask only for items under "
                "[preauth].never or genuine product decisions.")}
        else:
            run_log(cfg, f"question to human: {tail[:120]!r}")
            notify(cfg, "question", tail)
print(json.dumps(out))
sys.exit(0)
