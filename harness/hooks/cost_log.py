"""Per-session usage snapshot, appended on Stop / SubagentStop (ported from Puzzle's cost_log.py).

Sums the transcript's assistant `usage` records, deduplicated by requestId, and appends one
cumulative row to ~/.claude/metrics/harness-costs.jsonl (override HARNESS_COST_LOG). Later
rows for the same transcript supersede earlier ones. The ticket comes from the git branch,
matched against the project's [project].ticket_prefix.

Codex rollouts use a different record shape; they are skipped here and costed by
$HARNESS_ROOT/scripts/audit/audit.py instead. Never raises, never prints secrets.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import re
from pathlib import Path

LOG = Path(os.environ.get("HARNESS_COST_LOG", Path.home() / ".claude/metrics/harness-costs.jsonl"))


def summarize(path: Path, prefix: str) -> dict | None:
    seen: set[str] = set()
    tot: collections.Counter = collections.Counter()
    models: collections.Counter = collections.Counter()
    first = last = branch = None
    with path.open() as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            ts = r.get("timestamp")
            if ts:
                first = first or ts
                last = ts
            branch = r.get("gitBranch") or branch
            if r.get("type") != "assistant":
                continue
            msg = r.get("message") or {}
            rid = r.get("requestId") or msg.get("id")
            u = msg.get("usage")
            if not u or not rid or rid in seen:
                continue
            seen.add(rid)
            cc = u.get("cache_creation") or {}
            models[msg.get("model", "?")] += 1
            tot["input"] += u.get("input_tokens", 0)
            tot["cache_read"] += u.get("cache_read_input_tokens", 0)
            tot["cache_write_5m"] += cc.get("ephemeral_5m_input_tokens", 0)
            tot["cache_write_1h"] += cc.get("ephemeral_1h_input_tokens", 0)
            tot["output"] += u.get("output_tokens", 0)
            tot["max_context"] = max(tot["max_context"], u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                                     + cc.get("ephemeral_5m_input_tokens", 0) + cc.get("ephemeral_1h_input_tokens", 0))
    if not seen:
        return None
    m = re.search(rf"\b({re.escape(prefix)})-?(\d+)", branch or "", re.I) if prefix else None
    return dict(models=dict(models), **tot, first_ts=first, last_ts=last, git_branch=branch,
                ticket=f"{prefix}-{m.group(2)}" if m else None)


def log_usage(payload: dict, cfg: dict) -> None:
    try:
        tp = payload.get("agent_transcript_path") or payload.get("transcript_path")
        if not tp or not Path(tp).exists():
            return
        s = summarize(Path(tp), (cfg.get("project") or {}).get("ticket_prefix", ""))
        if not s:
            return
        row = dict(ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                   project=cfg.get("_root"), session_id=payload.get("session_id"), transcript=tp,
                   kind="subagent" if payload.get("agent_transcript_path") or "/subagents/" in tp else "main", **s)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:
        pass
