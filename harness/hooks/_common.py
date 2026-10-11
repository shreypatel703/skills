"""Shared plumbing for harness hooks. Works under Claude Code and Codex (same payload shape,
verified on Codex 0.160: `cwd`, `session_id`, `tool_name`, `tool_input`, `last_assistant_message`,
`stop_hook_active`). Codex sets no project-dir variable, so the project is found from `cwd`.

Every hook is a no-op outside a project that has docs/agents/harness.toml: the plugin is
installed globally, and a repo that never ran setup-harness must not be affected.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import harness_config  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
HARNESS_ROOT = PLUGIN_ROOT / "harness"


def read_payload() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def project(payload: dict) -> dict | None:
    """The merged config for the payload's project, or None when the project has no harness.toml."""
    cfg = harness_config.load(payload.get("cwd"))
    return cfg if cfg.get("_root") else None


def actor_id(payload: dict) -> str:
    """One id per agent: a subagent's own id when the payload carries one, else the session."""
    return str(payload.get("agent_id") or payload.get("session_id") or "unknown")


def counter(name: str, key: str, bump: bool = True) -> int:
    """A tiny per-actor counter kept in the temp dir (dies with the machine, which is fine)."""
    d = Path(tempfile.gettempdir()) / "harness-counters"
    d.mkdir(exist_ok=True)
    f = d / f"{name}-{key}".replace("/", "_")
    n = int(f.read_text() or 0) if f.exists() else 0
    if bump:
        n += 1
        f.write_text(str(n))
    return n


def run_log(cfg: dict, line: str) -> None:
    """Append one checkpoint line to <project>/<paths.state>/run.log (the passive status view)."""
    try:
        d = Path(cfg["_root"]) / harness_config.get(cfg, "paths.state", ".agent-state")
        d.mkdir(parents=True, exist_ok=True)
        ts = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        with (d / "run.log").open("a") as fh:
            fh.write(f"{ts} {line}\n")
    except Exception:
        pass


def notify(cfg: dict, kind: str, text: str) -> None:
    """Send one line through [notify].command when `kind` is enabled. Never raises, never blocks long."""
    cmd = harness_config.get(cfg, "notify.command", "")
    if not cmd or kind not in harness_config.get(cfg, "notify.on", []):
        return
    name = harness_config.get(cfg, "project.name", "") or Path(cfg["_root"]).name
    try:
        subprocess.run(cmd, shell=True, input=f"[{name}] {kind}: {text}"[:400], text=True, timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def block(reason: str) -> None:
    """Exit 2 blocks the tool call on both tools; stderr is what the agent sees."""
    print(f"[harness] {reason}", file=sys.stderr)
    sys.exit(2)
