# Harness

An orchestration harness for running ticket waves with subagents, built on the engineering
skills in this repo. The skills are identical in every project; what differs per project lives
in that project's `docs/agents/` folder, written by `setup-harness`:

| file | written by | read by | holds |
|---|---|---|---|
| `issue-tracker.md` | setup-matt-pocock-skills | the model | where tickets live; how to claim and resolve one |
| `domain.md` | setup-matt-pocock-skills | the model | which docs are truth |
| `landing.md` | setup-harness | the model | how verified work lands (PR or local merge) |
| `harness.toml` | setup-harness | the model **and the hooks** | tiers, runner, bounds, gate commands, phases, trust boundaries, pre-authorised actions |
| `checks/` | the project | the gate | checks only this project has |

Prose that needs judgment goes in markdown. Anything that must hold goes in `harness.toml`,
because the plugin's hooks enforce it there; a rule that only lives in prose gets broken (the
2026-10-04..11 audit found every prose-only bound violated somewhere, and no hook-enforced one).

## User-invoked

- **[setup-harness](./setup-harness/SKILL.md)**: Configure this repo for the harness (landing, gate, phases, routing, trust boundaries, pre-authorised actions). Run once, after setup-matt-pocock-skills.

## Model-invoked

- **[harness-orchestrator](./harness-orchestrator/SKILL.md)**: Run one bounded wave: select, size, brief, gate, review, post-review phases, land. Never implements itself.
- **[harness-implementer](./harness-implementer/SKILL.md)**: Implement one ticket or one blocker list in a given worktree; report in 15 lines.
- **[harness-reviewer](./harness-reviewer/SKILL.md)**: Standards + Spec review of a ticket diff, ending in the findings JSON; or targeted verify of named ids.
- **[harness-adr-reviewer](./harness-adr-reviewer/SKILL.md)**: One-round review of a docs-only decision record.
- **[harness-merge-resolver](./harness-merge-resolver/SKILL.md)**: Mechanical resolution of a stacked-branch conflict.
- **[harness-ui-tester](./harness-ui-tester/SKILL.md)**: Agent UI test of a built ticket against the project's scenarios, after review.
- **[harness-cost-audit](./harness-cost-audit/SKILL.md)**: What a window of Claude Code + Codex agent work cost and where it went.

## Hooks (`hooks/hooks.json`, both Claude Code and Codex)

All of them are no-ops in a project without `docs/agents/harness.toml`.

| event | script | does |
|---|---|---|
| SessionStart | `session_start.py` | exports `HARNESS_ROOT` (Claude), prints the harness and config paths |
| PreToolUse `Bash` | `pre_bash_guard.py` | blocks `--no-verify`, force pushes, pushing the default branch, sleep-polling, and full-suite reruns past `[bounds].full_suite_per_loop` |
| PreToolUse `Agent` | `pre_agent_guard.py` | broad-review cap per ticket; over-tier spawns warned or blocked per `[enforce].tiers` (briefs start with `Role:` and `Ticket:`) |
| Stop / SubagentStop | `stop_guard.py` | cost log; turns back a question that asks permission for a `[preauth].allowed` action; notifies on any other question |

Verified 2026-10-11: synthetic payload tests (27 cases) on both payload shapes, and the real
scripts under Codex 0.160 `codex exec`. Codex skips new plugin hooks until you trust them once
in `/hooks`. Codex sets no project-dir variable, so hooks find the project from the payload `cwd`.
