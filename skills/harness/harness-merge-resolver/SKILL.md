---
name: harness-merge-resolver
description: "Resolve a stacked-branch or integration merge in a worktree mechanically: probe with merge-tree, take both sides where hunks are disjoint, keep both migrations' chain consistent, run the gate, commit the merge. Use when the orchestrator reports a conflict between ticket branches or needs an integration base. Mechanical tier; never redesigns."
---

A merge is bookkeeping. You resolve exactly the conflicts git reports, keep both branches'
behaviour, and prove it with the gate. If a conflict needs a design choice, you stop and say
which one; you do not make it. The gate and paths come from `docs/agents/harness.toml`.

## Steps

1. `"$HARNESS_ROOT/scripts/merge-probe.sh" <base> <branch>…` (the plugin script; if the env var
   is unset, the session-start context names the path). It shows conflicting paths before you
   touch a worktree. No conflicts: tell the orchestrator a plain `git merge --no-ff` will do.
2. In the named worktree: `git merge --no-ff --no-edit <branch>`; `git diff --name-only --diff-filter=U`.
3. Per file, open the conflict hunks. Rules:
   - both sides add different functions/imports/rows: keep both, in the order of the base.
   - the changelog's unreleased section: keep both bullet sets, base's first.
   - the decision-record index (see `docs/agents/domain.md`): keep both rows in numeric order.
   - migrations: two heads means the branch merging *second* re-parents its parent revision to
     the other head (one new revision file if the chain would otherwise fork); then the
     project's "heads" command must print one head. Never delete a migration.
   - the same line changed both ways with different intent: **stop**, report the two hunks
     verbatim and the question; the orchestrator gets an owner ruling.
4. Run the gate (`[gate].command`, `{base}` = the base, `{tests}` = the modules both branches
   touch). It must be GREEN before you commit. Run each branch's named test modules once.
5. Commit the merge with the default merge subject plus a body listing every hand-resolved
   file and, for migrations, the new chain (`… → <rev a> → <rev b>`). Do not push, and never
   use `--no-verify`.

## Report (12 lines or fewer)

merge commit · resolved files (one line each: rule applied) · migration chain · gate result ·
open questions (verbatim hunks) or none.
