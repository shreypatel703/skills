# Landing: GitHub PRs

Verified work lands on `{default_branch}` through pull requests. A human approves and merges
every PR; agents never merge to `{default_branch}` and never push it.

## Per ticket

1. Push the ticket branch with `-u`.
2. Open a PR against the ticket's base: the branch below it in the stack, or `{default_branch}`
   when it is the bottom. Title: a conventional-commit subject.
3. The PR body carries, in this order:
   - **Trust boundary**: every changed file matching `[paths].trust_boundary` in
     `docs/agents/harness.toml`, so the reviewer reads those lines in full.
   - **Acceptance criteria**: each criterion with the reviewer's verdict id (St#/Sp#) that
     closed it.
   - **Tests**: added and changed counts, gate result, code-vs-test line split.
   - **Disclosures**: owner rulings, size overruns, MINOR findings deferred.
4. Comment on the ticket per `docs/agents/issue-tracker.md` with the PR link, and move it to the
   state that means "awaiting review".

## The stack

- Linear only: each ticket's base is the previous ticket's branch.
- Land bottom-up: once the bottom PR is merged, retarget the next one to `{default_branch}`
  (`gh pr edit <n> --base {default_branch}`), re-run the gate, and update its body.
- No more than `[bounds].max_unlanded_stack` unlanded PRs at once. At the limit, stop starting
  tickets and say which PR is waiting for review.
- Never replace a stack with one combined PR. A combined PR that no human can read is not landed.
