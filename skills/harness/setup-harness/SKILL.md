---
name: setup-harness
description: "Configure this repo for the harness skills and hooks: landing, gate commands, phases, model routing, trust boundaries and pre-authorised actions. Run once after setup-matt-pocock-skills."
disable-model-invocation: true
---

# Setup Harness

Writes the per-repo configuration the `harness-*` skills and the plugin's hooks read:

- `docs/agents/landing.md`: how verified work lands (prose, read by the model)
- `docs/agents/harness.toml`: numbers and commands (read by the model **and** by the hooks)
- a `### Harness` entry in the `## Agent skills` block of `CLAUDE.md` / `AGENTS.md`

Prose that needs judgment goes in markdown; anything a hook must enforce goes in the toml. A
rule that only lives in prose will be broken, so every bound the user cares about must land in
the toml.

This is a prompt-driven skill. Explore, present what you found, confirm, then write.

## 0. Precondition

`docs/agents/issue-tracker.md` and `docs/agents/domain.md` must exist. If either is missing, tell
the user to run `/setup-matt-pocock-skills` first and stop.

## 1. Explore

Read whatever exists; don't assume:

- `git remote -v`, the default branch, and whether it is protected (`gh api repos/{owner}/{repo}/branches/<default>/protection`, ignore errors).
- Gate and test commands: `Makefile`, `package.json` scripts, `pyproject.toml`, CI workflow
  files, any `scripts/**/review-gate*`, pre-commit config. Find the one command that runs lint +
  types + focused tests, and the one that runs the full suite.
- UI tests: Playwright/Cypress config, an `agent-tests/` or `e2e/` folder, a UI-test runbook.
- Existing harness material to fold in: `docs/agents/harness.md`, vendored `.claude/skills/pzl-*`
  or `.agents/skills/*` copies, `.codex/agents/*.toml`, `.codex/hooks.json`.
- Trust-boundary code: auth, tenancy filters, migrations, deletion or bulk-write paths,
  dependency manifests.
- An existing `docs/agents/harness.toml`: update it in place, never overwrite user edits.

## 2. Present findings and ask

One section, one answer, then the next. Lead with the recommended answer; skip a section the
exploration already settled.

**A. Landing.** Protected default branch with PRs: **github-pr** (recommended when a remote
exists). No remote or a solo repo: **local-merge**. Say plainly when the repo has no remote: the
work exists on one disk.

**B. Gate.** Propose `[gate].command` (must accept `{base}` and `{tests}`), `[gate].full_suite`,
and any project-only checks for `[gate].extra_checks` (move them to `docs/agents/checks/`).

**C. Phases.** If UI tests exist, ask whether UI tickets get an agent UI test after review; if
yes, set `[phases].after_review = ["ui_test"]` and fill `[ui_test]`.

**D. Routing.** Recommend the template's tiers unchanged. Ask one question: which tool runs which
role (`[runner]`), for example Codex for `ui_tester`. If any role runs on Codex, also do step 5.

**E. Trust boundaries.** Propose `[paths].trust_boundary` globs from what you found. These are
the lines a human reads in every PR.

**F. Pre-authorised actions.** Show `[preauth].allowed` and `[preauth].never` from the template;
ask "keep these?" (recommended: yes). Edit the matching `*_patterns` when the user changes a list.

**G. Notifications.** Ask whether they want a push when an agent asks a question or a gate goes
red; if yes, take a command that reads one line on stdin (e.g. an ntfy or Slack webhook curl).
Never write a secret into the toml: reference an env var the command reads.

## 3. Confirm and write

Show drafts of all three outputs; let the user edit; then write:

- `docs/agents/harness.toml`: start from [harness.toml](./harness.toml) (it is also the plugin's
  defaults), fill `[project]` and every answer above, and delete keys left at their default so
  the project file shows only what differs.
- `docs/agents/landing.md` from [landing-github-pr.md](./landing-github-pr.md) or
  [landing-local-merge.md](./landing-local-merge.md), filling its `{placeholders}`. For a repo
  with no remote, `{backup_line}` names the risk and the remote to add.
- In the `## Agent skills` block (same file-selection rules as setup-matt-pocock-skills):

  ```markdown
  ### Harness

  [landing in one line]; bounds, routing and gate in `docs/agents/harness.toml`. See `docs/agents/landing.md`.
  ```

Add `[paths].state` and `[paths].digests` to `.gitignore`.

## 4. Remove the copies

List every vendored copy of these skills or of the old harness scripts you found (for example
`.claude/skills/pzl-*`, `.agents/skills/*`, a `.codex/hooks.json` that calls project scripts).
Ask before deleting; on yes, delete them in the same change. A project that keeps a copy drifts
from the plugin, which is the problem this skill exists to fix.

## 5. Codex

If any `[runner]` entry is `codex`, or the user runs this repo from Codex:

- Profiles are files, not tables: `codex exec -p <name>` layers `~/.codex/<name>.config.toml` on
  `config.toml` (`[profiles.x]` tables are ignored since Codex 0.134). Show the user three small
  files to create: `mechanical.config.toml`, `default.config.toml`, `frontier.config.toml`, each
  with `model = ...` and `model_reasoning_effort = ...`. Do not write files under `~/.codex`
  yourself.
- Remind the user that Codex skips new plugin hooks until they are reviewed: open `/hooks` in
  Codex once and trust the harness hooks.

## 6. Done

Tell the user what was written, which `harness-*` skills now read it, and that
`<[paths].state>/run.log` is where hooks record blocked actions and questions. They can edit
`docs/agents/*` directly; re-run this skill only to start over.
