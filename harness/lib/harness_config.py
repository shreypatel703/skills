"""Load the harness config: plugin defaults deep-merged with the project's docs/agents/harness.toml.

Project root resolution, in order:
  1. walk up from the hook payload's `cwd` (follows worktrees, which carry their own copy);
  2. $CLAUDE_PROJECT_DIR (the session's start directory; does not follow worktrees);
  3. the process cwd.
A project with no harness.toml gets the defaults, so a hook never crashes a session.

CLI: python3 harness_config.py [get <dotted.key> | dump | root] [--cwd DIR]
"""
from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULTS = HERE.parents[1] / "skills/harness/setup-harness/harness.toml"
REL = Path("docs/agents/harness.toml")


def find_root(start: str | os.PathLike | None = None) -> Path | None:
    candidates = [start, os.environ.get("CLAUDE_PROJECT_DIR"), os.getcwd()]
    for c in candidates:
        if not c:
            continue
        p = Path(c).resolve()
        for d in (p, *p.parents):
            if (d / REL).is_file():
                return d
    return None


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(start: str | os.PathLike | None = None) -> dict:
    cfg = tomllib.loads(DEFAULTS.read_text())
    root = find_root(start)
    if root:
        try:
            cfg = _merge(cfg, tomllib.loads((root / REL).read_text()))
        except tomllib.TOMLDecodeError as e:
            print(f"[harness] ignoring malformed {root / REL}: {e}", file=sys.stderr)
    cfg["_root"] = str(root) if root else None
    return cfg


def get(cfg: dict, dotted: str, default=None):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def model_for(cfg: dict, role: str, tool: str = "claude") -> str | None:
    tier = get(cfg, f"tiers.{role}")
    return get(cfg, f"models.{tool}.{tier}") if tier else None


if __name__ == "__main__":
    args = sys.argv[1:]
    cwd = None
    if "--cwd" in args:
        i = args.index("--cwd")
        cwd = args[i + 1]
        del args[i : i + 2]
    cfg = load(cwd)
    if not args or args[0] == "dump":
        print(json.dumps(cfg, indent=2))
    elif args[0] == "root":
        print(cfg["_root"] or "")
    elif args[0] == "get" and len(args) == 2:
        v = get(cfg, args[1])
        print(json.dumps(v) if isinstance(v, (dict, list)) else ("" if v is None else v))
    else:
        sys.exit(__doc__)
