#!/usr/bin/env python3
"""SessionStart: tell the agent where the harness lives and whether this project is configured.

Claude Code: exports HARNESS_ROOT through $CLAUDE_ENV_FILE so skills can run
"$HARNESS_ROOT/scripts/...". Codex has no env file, so the same path is printed as context.
"""
import os
import sys

from _common import HARNESS_ROOT, project, read_payload

payload = read_payload()
cfg = project(payload)
env_file = os.environ.get("CLAUDE_ENV_FILE")
if env_file:
    try:
        with open(env_file, "a") as fh:
            fh.write(f'export HARNESS_ROOT="{HARNESS_ROOT}"\n')
    except OSError:
        pass
if cfg:
    print(f"Harness: scripts at {HARNESS_ROOT}/scripts (HARNESS_ROOT); project config "
          f"{cfg['_root']}/docs/agents/harness.toml.")
sys.exit(0)
