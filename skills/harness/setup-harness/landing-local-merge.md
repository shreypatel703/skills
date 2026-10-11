# Landing: local merge

Verified work lands on `{integration_branch}` by a local merge. There is no PR review, so the
gate, the review loop and any post-review phases are the only checks: never merge with a RED
gate or an open BLOCKER.

## Per ticket

1. With the gate green and the review CLEAN, merge the ticket branch into
   `{integration_branch}` with `--no-ff`, message `merge: <ticket id> <title>`.
2. Run `[gate].full_suite` once on `{integration_branch}`. RED: revert the merge, reopen the
   ticket with the failing output, and continue with the next ticket.
3. Resolve the ticket per `docs/agents/issue-tracker.md`, quoting the merge commit.
4. Remove the ticket worktree after the merge; keep review reports under `[paths].state`, not
   inside the worktree, so they survive its removal.

## Backup

{backup_line}
