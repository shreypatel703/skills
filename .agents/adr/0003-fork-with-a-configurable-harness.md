# Fork with a configurable orchestration harness

Status: proposed (2026-10-11). Applies to this fork only, not to upstream mattpocock/skills.

## Context

Three projects (Puzzle, Cue, Career OS) each grew their own orchestration framework. Cue's was a
copy of Puzzle's `pzl-*` skills and `scripts/agents/` (7 of 10 scripts byte-identical); Career
OS's was a separate Codex design. The copies drifted (Cue's ADR-number collision came from a
forked script it did not use), the engineering skills were installed twice (vendored and as a
plugin), and every rule written only in prose was broken somewhere in the 2026-10-04..11 audit.

## Decision

- Fork mattpocock/skills and add a `skills/harness/` bucket plus `harness/` (hooks, scripts,
  config loader) and a root `hooks/hooks.json`. Upstream files are never edited, so
  `git merge upstream/main` stays clean.
- Per-project differences live only in the project's `docs/agents/`, extending upstream's own
  configuration pattern: markdown for judgment (`landing.md` next to upstream's
  `issue-tracker.md` and `domain.md`), `harness.toml` for numbers and commands.
- `skills/harness/setup-harness/harness.toml` is both the template and the hooks' defaults, so
  the two cannot drift.
- One plugin manifest (`.claude-plugin/plugin.json`, renamed `shrey-skills`) serves Claude Code
  and Codex (Codex reads it since 0.161; see ADR 0002's 2026-10-07 update). Hooks use
  `${CLAUDE_PLUGIN_ROOT}`, which Codex also sets for plugin hooks.
- Projects delete their vendored copies; `setup-harness` lists them and removes them on yes.

## Rejected options

- **Keep per-project forks of the skills.** That is the status quo that drifted.
- **Git submodule of a shared skills repo in each project.** It still puts a copy in every repo,
  pins versions per project by commit rather than by a reviewed release, and Codex drops symlinks.
- **Edit upstream skills in place.** Every upstream merge would conflict.
- **Configuration as prose only (upstream's pattern alone).** Prose cannot be enforced; the
  bounds that mattered were the ones broken.
- **Codex `[profiles.x]` tables for routing.** Ignored since Codex 0.134; profiles are
  `~/.codex/<name>.config.toml` files used with `codex exec -p`.

## Consequences

- A bad harness change reaches every project at once. Mitigation: plugin versions are
  `<upstream>-harness.N`; test a change in one project before tagging.
- Codex users must trust the plugin hooks once (`/hooks`) and run Codex 0.161 or newer.
- Hooks that read project files run in every repo where the plugin is enabled; they exit
  immediately without `docs/agents/harness.toml`.
